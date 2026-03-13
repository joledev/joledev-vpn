#!/usr/bin/env python3
"""VPS Monitor Telegram Bot - Main entry point."""

import os
import sys
import asyncio
import logging
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from notifiers import system_health, vpn_peers, k8s_pods, certificates, fail2ban, versions, daily_report
from utils.telegram import send_message

load_dotenv()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

AUTHORIZED_CHAT_ID = int(os.environ["TELEGRAM_CHAT_ID"])


def authorized(func):
    """Decorator to restrict commands to authorized chat only."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat.id != AUTHORIZED_CHAT_ID:
            await update.message.reply_text("⛔ No autorizado.")
            return
        return await func(update, context)
    return wrapper


@authorized
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 <b>JoleDevVPN Bot</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "Monitor del VPS srv908005\n\n"
        "📋 <b>Comandos disponibles:</b>\n\n"
        "🖥 /status — Estado del servidor\n"
        "🔐 /peers — Peers VPN activos\n"
        "☸️ /pods — Estado de pods K3s\n"
        "🔒 /certs — Certificados TLS\n"
        "🛡 /fail2ban — IPs baneadas\n"
        "📦 /versions — Versiones de software\n"
        "📊 /report — Reporte completo\n"
        "❓ /help — Mostrar esta ayuda"
    )
    await update.message.reply_text(text, parse_mode="HTML")


@authorized
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = system_health.get_status_text()
    await update.message.reply_text(text, parse_mode="HTML")


@authorized
async def cmd_peers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = vpn_peers.get_peers_text()
    await update.message.reply_text(text, parse_mode="HTML")


@authorized
async def cmd_pods(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = k8s_pods.get_pods_text()
    await update.message.reply_text(text, parse_mode="HTML")


@authorized
async def cmd_certs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = certificates.get_certs_text()
    await update.message.reply_text(text, parse_mode="HTML")


@authorized
async def cmd_fail2ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = fail2ban.get_fail2ban_text()
    await update.message.reply_text(text, parse_mode="HTML")


@authorized
async def cmd_versions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = versions.get_versions_text()
    await update.message.reply_text(text, parse_mode="HTML")


@authorized
async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = daily_report.generate_report()
    await update.message.reply_text(text, parse_mode="HTML")


@authorized
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, context)


def check_reboot_alert():
    """Send alert if VPS was recently rebooted."""
    import psutil
    import time

    boot_time = psutil.boot_time()
    uptime_secs = time.time() - boot_time
    if uptime_secs < 300:  # Less than 5 minutes
        from utils.formatting import header, footer
        from datetime import datetime

        now = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
        uptime_str = f"{int(uptime_secs // 60)} minutos"
        text = (
            f"🔄 VPS reiniciado\n"
            f"{header('')}\n"
            f"🖥 {os.environ.get('VPS_HOSTNAME', 'srv908005')}\n"
            f"⏱ Uptime: {uptime_str}\n"
            f"🕐 {now}\n"
            f"{footer('Todos los servicios iniciando...')}"
        )
        send_message(text)


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)

    # Check for reboot
    check_reboot_alert()

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("peers", cmd_peers))
    app.add_handler(CommandHandler("pods", cmd_pods))
    app.add_handler(CommandHandler("certs", cmd_certs))
    app.add_handler(CommandHandler("fail2ban", cmd_fail2ban))
    app.add_handler(CommandHandler("versions", cmd_versions))
    app.add_handler(CommandHandler("report", cmd_report))
    app.add_handler(CommandHandler("help", cmd_help))

    logger.info("Bot starting with polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
