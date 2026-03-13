#!/usr/bin/env python3
"""WireGuard VPN peers monitor."""

import os
import sys
import json
import time
import re
import urllib.request
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.system import run_kubectl
from utils.formatting import header, footer, format_bytes, format_duration
from utils.telegram import send_message

STATE_FILE = "/tmp/wg_peers_state.json"

HANDSHAKE_TIMEOUT = 120  # 2 minutes — consider disconnected after this


def load_wg_easy_config():
    """Load peer names from wg-easy's wg0.json config file.
    Returns dicts mapping public_key -> name and public_key -> address."""
    output = run_kubectl(
        "exec deployment/wg-easy -n joledev-vpn -- cat /etc/wireguard/wg0.json"
    )
    key_to_name = {}
    key_to_address = {}
    if not output:
        return key_to_name, key_to_address
    try:
        data = json.loads(output)
        for client in data.get("clients", {}).values():
            pub_key = client.get("publicKey", "")
            name = client.get("name", "")
            address = client.get("address", "")
            if pub_key:
                if name:
                    key_to_name[pub_key] = name
                if address:
                    key_to_address[pub_key] = address
    except json.JSONDecodeError:
        pass
    return key_to_name, key_to_address


def parse_wg_show():
    """Parse output of wg show to get peer info, enriched with wg-easy names."""
    output = run_kubectl(
        "exec deployment/wg-easy -n joledev-vpn -- wg show wg0"
    )
    if not output:
        return []

    # Load friendly names from wg-easy config
    key_to_name, key_to_address = load_wg_easy_config()

    peers = []
    current_peer = None

    for line in output.split("\n"):
        line = line.strip()
        if line.startswith("peer:"):
            if current_peer:
                peers.append(current_peer)
            pub_key = line.split("peer:")[1].strip()
            current_peer = {
                "public_key": pub_key,
                "endpoint": None,
                "allowed_ips": key_to_address.get(pub_key),
                "latest_handshake": None,
                "transfer_rx": 0,
                "transfer_tx": 0,
                "name": key_to_name.get(pub_key),
            }
        elif current_peer:
            if line.startswith("endpoint:"):
                current_peer["endpoint"] = line.split("endpoint:")[1].strip()
            elif line.startswith("allowed-ips:"):
                ips = line.split("allowed-ips:")[1].strip()
                for ip in ips.split(","):
                    ip = ip.strip().split("/")[0]
                    if ip.startswith("10.8.0."):
                        current_peer["allowed_ips"] = ip
                        break
            elif line.startswith("latest handshake:"):
                hs_str = line.split("latest handshake:")[1].strip()
                current_peer["latest_handshake"] = parse_handshake_time(hs_str)
            elif line.startswith("transfer:"):
                transfer = line.split("transfer:")[1].strip()
                parts = transfer.split(",")
                if len(parts) == 2:
                    current_peer["transfer_rx"] = parse_transfer(parts[0].strip())
                    current_peer["transfer_tx"] = parse_transfer(parts[1].strip())

    if current_peer:
        peers.append(current_peer)

    return peers


def parse_handshake_time(hs_str):
    """Parse handshake time string to epoch seconds."""
    if "never" in hs_str.lower() or not hs_str:
        return None

    total_seconds = 0
    parts = re.findall(r"(\d+)\s+(second|minute|hour|day)s?", hs_str)
    multipliers = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}
    for value, unit in parts:
        total_seconds += int(value) * multipliers.get(unit, 0)

    return time.time() - total_seconds


def parse_transfer(t_str):
    """Parse transfer string like '2.1 MiB' to bytes."""
    match = re.match(r"([\d.]+)\s*(\w+)", t_str)
    if not match:
        return 0
    value = float(match.group(1))
    unit = match.group(2).lower()
    multipliers = {"b": 1, "kib": 1024, "mib": 1024**2, "gib": 1024**3, "tib": 1024**4}
    return int(value * multipliers.get(unit, 1))


def get_peer_status(peer):
    """Determine if a peer is active."""
    if peer["latest_handshake"] is None:
        return "never"
    elapsed = time.time() - peer["latest_handshake"]
    if elapsed < HANDSHAKE_TIMEOUT:
        return "active"
    return "inactive"


def format_handshake_ago(peer):
    """Format time since last handshake."""
    if peer["latest_handshake"] is None:
        return "nunca conectado"
    elapsed = time.time() - peer["latest_handshake"]
    return f"hace {format_duration(elapsed)}"


def geolocate_ip(ip):
    """Get geolocation info for an IP."""
    try:
        req = urllib.request.Request(
            f"https://ipinfo.io/{ip}/json",
            headers={"Accept": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read())
        org = data.get("org", "")
        city = data.get("city", "")
        country = data.get("country", "")
        parts = [p for p in [city, country] if p]
        location = ", ".join(parts)
        return f"{org} — {location}" if org else location
    except Exception:
        return ""


def get_peers_text():
    """Generate peers status text for /peers command."""
    peers = parse_wg_show()
    if not peers:
        return "🔐 No se pudo obtener info de peers VPN"

    lines = [header("🔐 Peers VPN — Ahora")]
    active_count = 0

    for peer in sorted(peers, key=lambda p: p.get("allowed_ips", "z")):
        status = get_peer_status(peer)
        name = peer["name"] or peer["allowed_ips"] or "desconocido"
        ip = peer["allowed_ips"] or "?"
        ago = format_handshake_ago(peer)

        if status == "active":
            active_count += 1
            rx = format_bytes(peer["transfer_rx"])
            tx = format_bytes(peer["transfer_tx"])
            lines.append(f"🟢 {name}  {ip}  último: {ago}  ↑{tx} ↓{rx}")
        else:
            emoji = "🔴"
            lines.append(f"{emoji} {name}  {ip}  último: {ago}")

    lines.append(footer(f"{active_count}/{len(peers)} peers activos"))
    return "\n".join(lines)


def check_peer_changes():
    """Check for peer connection/disconnection changes and notify."""
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")

    peers = parse_wg_show()
    if not peers:
        return

    # Load previous state
    prev_state = {}
    try:
        with open(STATE_FILE) as f:
            prev_state = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    # Build current state
    current_state = {}
    for peer in peers:
        ip = peer["allowed_ips"] or peer["public_key"][:8]
        status = get_peer_status(peer)
        current_state[ip] = {
            "status": status,
            "name": peer["name"] or ip,
            "endpoint": peer["endpoint"],
            "transfer_rx": peer["transfer_rx"],
            "transfer_tx": peer["transfer_tx"],
            "timestamp": time.time(),
        }

    # Detect changes
    for ip, curr in current_state.items():
        prev = prev_state.get(ip, {})
        prev_status = prev.get("status", "unknown")
        curr_status = curr["status"]
        name = curr["name"]
        now_str = datetime.now().strftime("%I:%M %p")

        if prev_status != "active" and curr_status == "active":
            # Peer connected
            endpoint_ip = ""
            geo = ""
            if curr["endpoint"]:
                endpoint_ip = curr["endpoint"].split(":")[0]
                geo = geolocate_ip(endpoint_ip)

            text = (
                f"📱 Peer conectado al VPN\n"
                f"{header('')}\n"
                f"👤 {name}\n"
            )
            if endpoint_ip:
                text += f"🌐 Desde: {endpoint_ip}"
                if geo:
                    text += f" ({geo})"
                text += "\n"
            text += (
                f"📍 IP VPN: {ip}\n"
                f"🕐 {now_str}\n"
            )
            send_message(text)

        elif prev_status == "active" and curr_status != "active":
            # Peer disconnected
            prev_ts = prev.get("timestamp", time.time())
            duration = time.time() - prev_ts
            prev_rx = prev.get("transfer_rx", 0)
            prev_tx = prev.get("transfer_tx", 0)
            delta_rx = max(0, curr["transfer_rx"] - prev_rx)
            delta_tx = max(0, curr["transfer_tx"] - prev_tx)

            text = (
                f"📴 Peer desconectado del VPN\n"
                f"{header('')}\n"
                f"👤 {name}\n"
                f"⏱ Conectado por: {format_duration(duration)}\n"
                f"📊 Transferido: ↑{format_bytes(delta_tx)} ↓{format_bytes(delta_rx)}\n"
                f"🕐 {now_str}\n"
            )
            send_message(text)

    # Save current state
    with open(STATE_FILE, "w") as f:
        json.dump(current_state, f)


if __name__ == "__main__":
    check_peer_changes()
