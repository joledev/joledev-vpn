#!/usr/bin/env python3
"""Fail2ban monitor."""

import os
import sys
import json
import time
import re
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.system import run_cmd
from utils.formatting import header, footer
from utils.telegram import send_message

STATE_FILE = "/tmp/vps_fail2ban_state.json"


def get_banned_ips():
    """Get currently banned IPs from fail2ban."""
    # Try fail2ban-client (may need sudo)
    output = run_cmd("sudo fail2ban-client status sshd 2>/dev/null || fail2ban-client status sshd 2>/dev/null")
    if not output:
        # Fallback: parse iptables
        output = run_cmd("sudo iptables -L f2b-sshd -n 2>/dev/null || iptables -L f2b-sshd -n 2>/dev/null")
        if not output:
            return []
        # Parse iptables output for REJECT/DROP rules
        ips = []
        for line in output.split("\n"):
            match = re.search(r"(?:REJECT|DROP)\s+\S+\s+--\s+(\d+\.\d+\.\d+\.\d+)", line)
            if match:
                ips.append({"ip": match.group(1), "jail": "sshd"})
        return ips

    # Parse fail2ban-client output
    banned = []
    ban_match = re.search(r"Banned IP list:\s*(.*)", output)
    if ban_match:
        ip_list = ban_match.group(1).strip()
        if ip_list:
            for ip in ip_list.split():
                banned.append({"ip": ip.strip(), "jail": "sshd"})

    return banned


def geolocate_ip(ip):
    """Get country for an IP."""
    try:
        req = urllib.request.Request(
            f"https://ipinfo.io/{ip}/json",
            headers={"Accept": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read())
        country = data.get("country", "??")
        city = data.get("city", "")
        return country, city
    except Exception:
        return "??", ""


def get_fail2ban_text():
    """Generate fail2ban status text for /fail2ban command."""
    banned = get_banned_ips()

    lines = [header("🛡 Fail2ban — Bans activos")]

    if not banned:
        lines.append("✅ No hay IPs baneadas actualmente")
    else:
        for entry in banned:
            ip = entry["ip"]
            country, city = geolocate_ip(ip)
            location = f"{city}, {country}" if city else country
            lines.append(f"🚫 {ip}  ({entry['jail']}) — {location}")

    lines.append(footer(f"{len(banned)} IPs baneadas actualmente"))
    return "\n".join(lines)


def check_new_bans():
    """Check for newly banned IPs and notify."""
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")

    banned = get_banned_ips()
    current_ips = {b["ip"] for b in banned}

    # Load previous state
    prev_ips = set()
    try:
        with open(STATE_FILE) as f:
            state = json.load(f)
            prev_ips = set(state.get("banned_ips", []))
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    # Detect new bans
    new_bans = current_ips - prev_ips
    for ip in new_bans:
        country, city = geolocate_ip(ip)
        location = f"{city}, {country}" if city else country

        text = (
            f"🚫 IP baneada por Fail2ban\n"
            f"{header('')}\n"
            f"🌐 {ip}\n"
            f"🔍 País: {location}\n"
            f"⚠️ Razón: SSH brute force\n"
            f"🕐 Ahora\n"
        )
        send_message(text)

    # Save state
    with open(STATE_FILE, "w") as f:
        json.dump({"banned_ips": list(current_ips), "timestamp": time.time()}, f)


if __name__ == "__main__":
    check_new_bans()
