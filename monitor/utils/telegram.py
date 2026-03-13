import os
import urllib.request
import json


def get_token():
    return os.environ["TELEGRAM_BOT_TOKEN"]


def get_chat_id():
    return os.environ["TELEGRAM_CHAT_ID"]


def send_message(text, parse_mode="HTML"):
    """Send a message via Telegram Bot API (no dependencies needed)."""
    token = get_token()
    chat_id = get_chat_id()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"Error sending Telegram message: {e}")
