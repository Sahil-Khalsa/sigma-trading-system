"""
Central notification dispatcher.
All events in SIGMA flow through notify_*() helpers here.
Notifications are fire-and-forget (errors are logged, never raised).
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Runtime-injected config — set in main.py after settings load
_telegram_token: Optional[str] = None
_telegram_chat_id: Optional[str] = None
_smtp_host: Optional[str] = None
_smtp_port: int = 587
_smtp_user: Optional[str] = None
_smtp_password: Optional[str] = None
_notification_email: Optional[str] = None

# In-memory log for the dashboard (last 200 alerts)
_alert_log: list[dict] = []
MAX_LOG = 200


def configure(
    telegram_token: Optional[str] = None,
    telegram_chat_id: Optional[str] = None,
    smtp_host: Optional[str] = None,
    smtp_port: int = 587,
    smtp_user: Optional[str] = None,
    smtp_password: Optional[str] = None,
    notification_email: Optional[str] = None,
):
    global _telegram_token, _telegram_chat_id
    global _smtp_host, _smtp_port, _smtp_user, _smtp_password, _notification_email
    _telegram_token = telegram_token
    _telegram_chat_id = telegram_chat_id
    _smtp_host = smtp_host
    _smtp_port = smtp_port
    _smtp_user = smtp_user
    _smtp_password = smtp_password
    _notification_email = notification_email


def get_alert_log() -> list[dict]:
    return list(_alert_log)


def _add_log(level: str, title: str, body: str):
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "title": title,
        "body": body,
    }
    _alert_log.append(entry)
    if len(_alert_log) > MAX_LOG:
        _alert_log.pop(0)


async def _tg(text: str):
    if not (_telegram_token and _telegram_chat_id):
        return
    from notifications.telegram import send_telegram
    await send_telegram(_telegram_token, _telegram_chat_id, text)


def _email(subject: str, html_body: str):
    if not (_smtp_host and _smtp_user and _smtp_password and _notification_email):
        return
    from notifications.email_notifier import send_email
    send_email(
        _smtp_host, _smtp_port, _smtp_user, _smtp_password,
        _notification_email, subject, html_body,
    )


# ─── Public event helpers ────────────────────────────────────────────────────

async def notify_signal_fired(symbol: str, signal_type: str, value: float, price: float):
    msg = f"<b>📡 Signal Fired</b>\n<b>{symbol}</b> — {signal_type.replace('_', ' ').title()}\nValue: {value:.2f}  |  Price: ${price:.2f}"
    _add_log("info", f"Signal: {symbol} {signal_type}", f"value={value:.2f} price=${price:.2f}")
    asyncio.create_task(_tg(msg))


async def notify_trade_executed(
    symbol: str, direction: str, qty: float, entry: float,
    target: float, stop: float, confidence: float,
):
    emoji = "🟢" if direction == "LONG" else "🔴"
    msg = (
        f"<b>{emoji} Trade Executed</b>\n"
        f"<b>{direction} {symbol}</b>  qty={qty:.2f}\n"
        f"Entry: ${entry:.2f}  |  Target: ${target:.2f}  |  Stop: ${stop:.2f}\n"
        f"Confidence: {confidence:.0%}"
    )
    _add_log("success", f"Trade: {direction} {symbol}", f"qty={qty:.2f} @ ${entry:.2f} conf={confidence:.0%}")
    asyncio.create_task(_tg(msg))


async def notify_trade_blocked(symbol: str, reason: str):
    msg = f"<b>🚫 Trade Blocked</b>\n<b>{symbol}</b>\nReason: {reason}"
    _add_log("warning", f"Blocked: {symbol}", reason)
    asyncio.create_task(_tg(msg))


async def notify_position_closed(
    symbol: str, direction: str, pnl_usd: float, pnl_pct: float, exit_reason: str
):
    emoji = "✅" if pnl_usd >= 0 else "❌"
    sign = "+" if pnl_usd >= 0 else ""
    msg = (
        f"<b>{emoji} Position Closed</b>\n"
        f"<b>{direction} {symbol}</b>\n"
        f"P&L: {sign}${pnl_usd:.2f}  ({sign}{pnl_pct*100:.2f}%)\n"
        f"Reason: {exit_reason}"
    )
    level = "success" if pnl_usd >= 0 else "error"
    _add_log(level, f"Closed: {symbol}", f"{sign}${pnl_usd:.2f} ({sign}{pnl_pct*100:.2f}%) — {exit_reason}")
    asyncio.create_task(_tg(msg))


async def notify_daily_limit_hit(current_loss_pct: float):
    msg = (
        f"<b>⛔ Daily Loss Limit Reached</b>\n"
        f"Current daily loss: {current_loss_pct*100:.2f}%\n"
        f"Trading halted for the day."
    )
    _add_log("error", "Daily Limit Hit", f"Loss: {current_loss_pct*100:.2f}% — trading halted")
    asyncio.create_task(_tg(msg))
    # Also email for daily limit — this is critical
    subject = "⛔ SIGMA: Daily Loss Limit Reached"
    html = f"<h2>Daily Loss Limit Reached</h2><p>Current daily loss: <b>{current_loss_pct*100:.2f}%</b></p><p>All trading has been halted for the day.</p>"
    asyncio.get_event_loop().run_in_executor(None, _email, subject, html)


async def notify_agent_passed(symbol: str, reason: str):
    _add_log("info", f"Passed: {symbol}", reason)


def notify_daily_digest(report_html: str):
    """Called by the scheduler every evening."""
    subject = f"SIGMA Daily Report — {datetime.now().strftime('%Y-%m-%d')}"
    _email(subject, report_html)
    _add_log("info", "Daily Digest Sent", "Email report dispatched")
