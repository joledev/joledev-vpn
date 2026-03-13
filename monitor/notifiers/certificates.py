#!/usr/bin/env python3
"""TLS certificates monitor."""

import os
import sys
import json
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.system import run_kubectl
from utils.formatting import header, footer
from utils.telegram import send_message


def get_certificates():
    """Get all certificates from cert-manager."""
    output = run_kubectl("get certificate -A -o json")
    if not output:
        return []

    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return []

    certs = []
    for item in data.get("items", []):
        ns = item["metadata"]["namespace"]
        name = item["metadata"]["name"]
        ready = False
        not_after = None

        for cond in item.get("status", {}).get("conditions", []):
            if cond.get("type") == "Ready" and cond.get("status") == "True":
                ready = True

        not_after_str = item.get("status", {}).get("notAfter")
        if not_after_str:
            try:
                not_after = datetime.fromisoformat(not_after_str.replace("Z", "+00:00"))
            except Exception:
                pass

        # Get DNS names
        dns_names = item.get("spec", {}).get("dnsNames", [])

        certs.append({
            "namespace": ns,
            "name": name,
            "ready": ready,
            "not_after": not_after,
            "dns_names": dns_names,
        })

    return certs


def get_certs_text():
    """Generate certificates status text for /certs command."""
    certs = get_certificates()
    if not certs:
        return "🔐 No se pudo obtener info de certificados"

    warning_days = int(os.environ.get("CERT_WARNING_DAYS", 14))
    now = datetime.now(timezone.utc)
    lines = [header("🔐 Certificados TLS")]

    for cert in sorted(certs, key=lambda c: c["dns_names"][0] if c["dns_names"] else c["name"]):
        domain = cert["dns_names"][0] if cert["dns_names"] else cert["name"]
        if cert["not_after"]:
            days_left = (cert["not_after"] - now).days
            if days_left <= 0:
                emoji = "🔴"
                suffix = " ← EXPIRADO"
            elif days_left <= warning_days:
                emoji = "⚠️"
                suffix = " ← RENOVAR PRONTO"
            else:
                emoji = "✅"
                suffix = ""
            lines.append(f"{emoji} {domain:<30} {days_left} días{suffix}")
        else:
            lines.append(f"❓ {domain:<30} (sin fecha)")

    lines.append(footer())
    return "\n".join(lines)


def check_expiring_certs():
    """Check for certificates expiring soon and notify."""
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")

    certs = get_certificates()
    if not certs:
        return

    warning_days = int(os.environ.get("CERT_WARNING_DAYS", 14))
    now = datetime.now(timezone.utc)
    expiring = []

    for cert in certs:
        if cert["not_after"]:
            days_left = (cert["not_after"] - now).days
            if days_left <= warning_days:
                domain = cert["dns_names"][0] if cert["dns_names"] else cert["name"]
                expiring.append((domain, days_left))

    if expiring:
        lines = [f"⚠️ Certificados próximos a vencer\n{header('')}"]
        for domain, days in sorted(expiring, key=lambda x: x[1]):
            emoji = "🔴" if days <= 0 else "⚠️"
            lines.append(f"{emoji} {domain} — {days} días restantes")
        lines.append(footer("Verificar cert-manager"))
        send_message("\n".join(lines))


if __name__ == "__main__":
    check_expiring_certs()
