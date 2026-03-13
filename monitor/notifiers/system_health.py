#!/usr/bin/env python3
"""System health monitor — CPU, RAM, disk, uptime."""

import os
import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import psutil
from utils.formatting import header, footer, format_bytes, format_duration
from utils.telegram import send_message

STATE_FILE = "/tmp/vps_health_state.json"


def get_system_info():
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count()
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    boot_time = psutil.boot_time()
    uptime = time.time() - boot_time
    load_1, load_5, load_15 = os.getloadavg()

    return {
        "cpu_percent": cpu_percent,
        "cpu_count": cpu_count,
        "ram_percent": mem.percent,
        "ram_used_gb": mem.used / (1024**3),
        "ram_total_gb": mem.total / (1024**3),
        "disk_percent": disk.percent,
        "disk_used_gb": disk.used / (1024**3),
        "disk_total_gb": disk.total / (1024**3),
        "disk_free_gb": disk.free / (1024**3),
        "uptime": uptime,
        "load_1": load_1,
        "load_5": load_5,
        "load_15": load_15,
    }


def get_status_text():
    info = get_system_info()
    hostname = os.environ.get("VPS_HOSTNAME", "srv908005")

    # Determine overall status
    status = "🟢 Todo nominal"
    if info["cpu_percent"] > 80 or info["ram_percent"] > 85 or info["disk_percent"] > 90:
        status = "🟡 Atención requerida"
    if info["cpu_percent"] > 95 or info["ram_percent"] > 95 or info["disk_percent"] > 95:
        status = "🔴 Estado crítico"

    text = (
        f"🖥 {hostname} — Estado actual\n"
        f"{header('')}\n"
        f"⚙️ CPU:    {info['cpu_percent']:.0f}% ({info['cpu_count']} vCPUs)\n"
        f"🧠 RAM:    {info['ram_percent']:.0f}% — {info['ram_used_gb']:.1f}/{info['ram_total_gb']:.1f} GB\n"
        f"💾 Disco:  {info['disk_percent']:.0f}% — {info['disk_used_gb']:.0f}/{info['disk_total_gb']:.0f} GB\n"
        f"⏱ Uptime: {format_duration(info['uptime'])}\n"
        f"📡 Load:   {info['load_1']:.2f}, {info['load_5']:.2f}, {info['load_15']:.2f}\n"
        f"{footer(status)}"
    )
    return text


def check_thresholds():
    """Check if any threshold is exceeded and send alert."""
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")

    info = get_system_info()
    cpu_threshold = int(os.environ.get("ALERT_CPU_THRESHOLD", 80))
    ram_threshold = int(os.environ.get("ALERT_RAM_THRESHOLD", 85))
    disk_threshold = int(os.environ.get("ALERT_DISK_THRESHOLD", 90))
    hostname = os.environ.get("VPS_HOSTNAME", "srv908005")

    # Load previous state for CPU sustained check
    cpu_high_count = 0
    try:
        with open(STATE_FILE) as f:
            state = json.load(f)
            cpu_high_count = state.get("cpu_high_count", 0)
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    alerts = []

    if info["cpu_percent"] > cpu_threshold:
        cpu_high_count += 1
        if cpu_high_count >= 3:  # 3 consecutive checks (15 min at 5min interval)
            alerts.append(f"⚙️ CPU al {info['cpu_percent']:.0f}% — sostenido {cpu_high_count * 5}min")
    else:
        cpu_high_count = 0

    if info["ram_percent"] > ram_threshold:
        alerts.append(f"🧠 RAM al {info['ram_percent']:.0f}% — {info['ram_used_gb']:.1f}/{info['ram_total_gb']:.1f} GB")

    if info["disk_percent"] > disk_threshold:
        alerts.append(f"💾 Disco al {info['disk_percent']:.0f}% — {info['disk_free_gb']:.0f} GB libres")

    # Save state
    with open(STATE_FILE, "w") as f:
        json.dump({"cpu_high_count": cpu_high_count, "timestamp": time.time()}, f)

    if alerts:
        text = (
            f"⚠️ Alerta de recursos — {hostname}\n"
            f"{header('')}\n"
            + "\n".join(alerts) + "\n"
            f"{footer('Revisar con /status')}"
        )
        send_message(text)
        return True
    return False


if __name__ == "__main__":
    check_thresholds()
