#!/usr/bin/env python3
"""Daily report generator."""

import os
import sys
import re
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

import psutil

from utils.system import run_cmd, run_kubectl
from utils.formatting import header, footer, format_bytes, format_duration
from utils.telegram import send_message
from notifiers import system_health, vpn_peers, k8s_pods, certificates, fail2ban


def generate_report():
    """Generate the full daily report."""
    hostname = os.environ.get("VPS_HOSTNAME", "srv908005")
    now = datetime.now()
    # Day names in Spanish
    days_es = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    months_es = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    day_name = days_es[now.weekday()]
    month_name = months_es[now.month - 1]
    date_str = f"{day_name} {now.day} {month_name} {now.year}"

    # System info
    info = system_health.get_system_info()

    # Pods
    pods = k8s_pods.get_all_pods()
    pods_non_system = [p for p in pods if p["namespace"] not in k8s_pods.SKIP_NAMESPACES]
    healthy_pods = sum(1 for p in pods_non_system if p["status"] in ("Running", "Succeeded", "Completed"))
    total_pods = len(pods_non_system)
    restart_pods = [(p["app"], p["namespace"]) for p in pods_non_system if p["restarts"] > 0]

    # Peers
    peers = vpn_peers.parse_wg_show()
    active_peers = [p for p in peers if vpn_peers.get_peer_status(p) == "active"]
    active_names = [p["name"] or p["allowed_ips"] for p in active_peers]
    total_rx = sum(p["transfer_rx"] for p in peers)
    total_tx = sum(p["transfer_tx"] for p in peers)

    # Fail2ban
    banned = fail2ban.get_banned_ips()

    # SSH failed attempts (try auth.log first, fallback to journalctl)
    ssh_fails = run_cmd("grep -c 'Failed password' /var/log/auth.log 2>/dev/null || sudo journalctl -u sshd --since '24 hours ago' 2>/dev/null | grep -c 'Failed password' || echo 0")
    try:
        ssh_fail_count = int(ssh_fails)
    except ValueError:
        ssh_fail_count = 0

    # Certificates
    certs = certificates.get_certificates()
    cert_issues = []
    warning_days = int(os.environ.get("CERT_WARNING_DAYS", 14))
    if certs:
        from datetime import timezone
        now_utc = datetime.now(timezone.utc)
        for cert in certs:
            if cert["not_after"]:
                days_left = (cert["not_after"] - now_utc).days
                if days_left <= warning_days:
                    domain = cert["dns_names"][0] if cert["dns_names"] else cert["name"]
                    cert_issues.append(f"{domain} ({days_left} días)")

    # Build report
    lines = [
        f"📊 Reporte Diario — {hostname}",
        header(""),
        f"📅 {date_str}",
        "",
        "🖥 SISTEMA",
        f"  CPU: {info['cpu_percent']:.0f}%",
        f"  RAM: {info['ram_percent']:.0f}% en uso",
        f"  Disco: {info['disk_percent']:.0f}% ({info['disk_free_gb']:.0f}GB libres)",
        f"  Uptime: {format_duration(info['uptime'])}",
        "",
        "🔐 VPN",
        f"  Peers activos ahora: {', '.join(active_names) if active_names else 'ninguno'}",
        f"  Tráfico total: ↑{format_bytes(total_tx)} ↓{format_bytes(total_rx)}",
        "",
        "☸️ K3S",
        f"  Pods running: {healthy_pods}/{total_pods}",
    ]

    if restart_pods:
        restarts_str = ", ".join(f"{app} ({ns})" for app, ns in restart_pods)
        lines.append(f"  Con reinicios: {restarts_str}")

    lines.extend([
        "",
        "🛡 SEGURIDAD",
        f"  IPs baneadas: {len(banned)}",
        f"  Intentos SSH fallidos (24h): {ssh_fail_count}",
    ])

    if cert_issues:
        lines.extend([
            "",
            "🔐 CERTIFICADOS",
            f"  Próximos a vencer: {', '.join(cert_issues)}",
        ])
    else:
        lines.extend([
            "",
            "🔐 CERTIFICADOS",
            "  Todos OK ✅",
        ])

    # Overall status
    is_ok = healthy_pods == total_pods and not cert_issues
    status = "Todo nominal ✅" if is_ok else "⚠️ Requiere atención"
    lines.append(footer(status))

    return "\n".join(lines)


def send_daily_report():
    """Send the daily report."""
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")

    text = generate_report()
    send_message(text)


if __name__ == "__main__":
    send_daily_report()
