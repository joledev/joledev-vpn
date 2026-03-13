#!/bin/bash
# Send a simple message via Telegram Bot API
# Usage: send_telegram.sh "Your message here"
set -euo pipefail

if [ -z "${1:-}" ]; then
    echo "Usage: $0 <message>"
    exit 1
fi

# Load env if not already set
if [ -z "${TELEGRAM_BOT_TOKEN:-}" ]; then
    export $(grep -v '^#' /home/joel/vps-monitor/.env | xargs)
fi

MESSAGE="$1"

curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -H "Content-Type: application/json" \
    -d "{\"chat_id\": \"${TELEGRAM_CHAT_ID}\", \"text\": \"${MESSAGE}\"}" \
    > /dev/null
