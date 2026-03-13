#!/bin/bash
# Check system health thresholds — called by cron
set -euo pipefail

cd /home/joel/vps-monitor
export $(grep -v '^#' .env | xargs)
/usr/bin/python3 /home/joel/vps-monitor/notifiers/system_health.py
