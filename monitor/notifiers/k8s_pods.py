#!/usr/bin/env python3
"""K3s pods monitor."""

import os
import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.system import run_kubectl
from utils.formatting import header, footer, format_duration
from utils.telegram import send_message

STATE_FILE = "/tmp/vps_pods_state.json"

# Namespaces to skip in output (internal K3s stuff)
SKIP_NAMESPACES = {"kube-system"}

BAD_PHASES = {"CrashLoopBackOff", "Error", "ImagePullBackOff", "ErrImagePull", "Failed"}


def get_all_pods():
    """Get all pods across all namespaces."""
    output = run_kubectl("get pods -A -o json")
    if not output:
        return []

    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return []

    pods = []
    for item in data.get("items", []):
        ns = item["metadata"]["namespace"]
        name = item["metadata"]["name"]
        # Get the short name (deployment name, without the hash suffix)
        labels = item["metadata"].get("labels", {})
        app_name = labels.get("app", labels.get("app.kubernetes.io/name", name))

        status = item["status"].get("phase", "Unknown")
        # Check container statuses for more specific status
        container_statuses = item["status"].get("containerStatuses", [])
        restarts = 0
        for cs in container_statuses:
            restarts += cs.get("restartCount", 0)
            waiting = cs.get("state", {}).get("waiting", {})
            if waiting.get("reason"):
                status = waiting["reason"]

        # Calculate age
        creation = item["metadata"].get("creationTimestamp", "")
        age = ""
        if creation:
            from datetime import datetime, timezone
            try:
                created = datetime.fromisoformat(creation.replace("Z", "+00:00"))
                delta = datetime.now(timezone.utc) - created
                age = format_duration(delta.total_seconds())
            except Exception:
                pass

        pods.append({
            "namespace": ns,
            "name": name,
            "app": app_name,
            "status": status,
            "restarts": restarts,
            "age": age,
        })

    return pods


def get_pods_text():
    """Generate pods status text for /pods command."""
    pods = get_all_pods()
    if not pods:
        return "☸️ No se pudo obtener info de pods"

    lines = [header("☸️ Pods K3s — Estado")]
    healthy = 0
    total = 0

    for pod in sorted(pods, key=lambda p: (p["namespace"], p["app"])):
        if pod["namespace"] in SKIP_NAMESPACES:
            continue
        total += 1
        is_ok = pod["status"] in ("Running", "Succeeded", "Completed")
        if is_ok:
            healthy += 1
        emoji = "✅" if is_ok else "❌"
        ns = pod["namespace"]
        app = pod["app"]
        status = pod["status"]
        age = pod["age"]
        line = f"{emoji} {ns:<16} {app:<18} {status:<12} {age}"
        lines.append(line)

    lines.append(footer(f"{healthy}/{total} pods healthy"))
    return "\n".join(lines)


def check_pod_issues():
    """Check for crashed/errored pods and notify."""
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")

    pods = get_all_pods()
    if not pods:
        return

    # Load previous state (to avoid duplicate alerts)
    prev_alerted = set()
    try:
        with open(STATE_FILE) as f:
            state = json.load(f)
            prev_alerted = set(state.get("alerted_pods", []))
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    current_bad = set()
    for pod in pods:
        if pod["status"] in BAD_PHASES:
            pod_key = f"{pod['namespace']}/{pod['name']}"
            current_bad.add(pod_key)

            if pod_key not in prev_alerted:
                # Get last few log lines
                logs = run_kubectl(
                    f"logs {pod['name']} -n {pod['namespace']} --tail=5",
                    timeout=10,
                )
                log_text = logs[:500] if logs else "(sin logs disponibles)"

                text = (
                    f"🔴 Pod caído en K3s\n"
                    f"{header('')}\n"
                    f"📦 {pod['app']} (namespace: {pod['namespace']})\n"
                    f"❌ Estado: {pod['status']}\n"
                    f"🔄 Reinicios: {pod['restarts']}\n"
                    f"📋 Últimas líneas de log:\n"
                    f"<code>{log_text}</code>\n"
                    f"{footer(f\"kubectl logs {pod['name']} -n {pod['namespace']}\")}"
                )
                send_message(text)

    # Save state
    with open(STATE_FILE, "w") as f:
        json.dump({"alerted_pods": list(current_bad), "timestamp": time.time()}, f)


if __name__ == "__main__":
    check_pod_issues()
