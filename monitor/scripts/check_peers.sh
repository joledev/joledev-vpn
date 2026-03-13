#!/bin/bash
# Check WireGuard peer changes — called by systemd timer
set -euo pipefail

cd /home/joel/vps-monitor
export $(grep -v '^#' .env | xargs)
/usr/bin/python3 /home/joel/vps-monitor/notifiers/vpn_peers.py
