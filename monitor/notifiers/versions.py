#!/usr/bin/env python3
"""Software versions checker."""

import os
import sys
import json
import re
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.system import run_cmd, run_kubectl
from utils.formatting import header, footer
from utils.telegram import send_message

GITHUB_REPOS = {
    "k3s": "k3s-io/k3s",
    "wg-easy": "wg-easy/wg-easy",
    "traefik": "traefik/traefik",
}


def get_latest_github_release(repo):
    """Get latest release version from GitHub API."""
    try:
        url = f"https://api.github.com/repos/{repo}/releases/latest"
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github.v3+json"})
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        return data.get("tag_name", "").lstrip("v")
    except Exception:
        return None


def get_current_versions():
    """Get currently installed versions."""
    versions = {}

    # K3s
    k3s_output = run_cmd("k3s --version 2>/dev/null")
    if k3s_output:
        match = re.search(r"v([\d.]+)", k3s_output)
        if match:
            versions["k3s"] = match.group(1)

    # wg-easy - get from container image tag
    wg_output = run_kubectl(
        "get deployment wg-easy -n joledev-vpn -o jsonpath='{.spec.template.spec.containers[0].image}'"
    )
    if wg_output:
        # Extract version from image tag
        match = re.search(r":v?(\d+[\d.]*)", wg_output)
        if match:
            versions["wg-easy"] = match.group(1)
        elif "latest" in wg_output:
            versions["wg-easy"] = "latest"

    # Traefik
    traefik_output = run_kubectl(
        "get deployment traefik -n kube-system -o jsonpath='{.spec.template.spec.containers[0].image}'"
    )
    if traefik_output:
        match = re.search(r":(v?[\d.]+)", traefik_output)
        if match:
            versions["traefik"] = match.group(1).lstrip("v")

    return versions


def get_versions_text():
    """Generate versions status text for /versions command."""
    current = get_current_versions()
    lines = [header("📦 Versiones")]

    for name, repo in GITHUB_REPOS.items():
        curr = current.get(name, "?")
        latest = get_latest_github_release(repo)

        if latest and curr != "?" and curr != "latest":
            # Normalize for comparison
            curr_clean = curr.split("+")[0]  # Remove +k3s1 suffix
            latest_clean = latest.split("+")[0]
            if curr_clean == latest_clean:
                lines.append(f"{name:<12} v{curr:<10} ✅ última")
            else:
                lines.append(f"{name:<12} v{curr:<10} 🆕 v{latest} disponible")
        elif latest:
            lines.append(f"{name:<12} {curr:<10} (última: v{latest})")
        else:
            lines.append(f"{name:<12} v{curr:<10} ❓ no se pudo verificar")

    lines.append(footer())
    return "\n".join(lines)


def check_outdated():
    """Check for outdated versions and notify."""
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")

    text = get_versions_text()
    if "🆕" in text:
        send_message(text)


if __name__ == "__main__":
    check_outdated()
