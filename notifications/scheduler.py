"""
Daily digest scheduler — fires at 4:15 PM EST every trading day.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta

import pytz

logger = logging.getLogger(__name__)
EST = pytz.timezone("America/New_York")


def _seconds_until_next_digest() -> float:
    now_est = datetime.now(EST)
    target = now_est.replace(hour=16, minute=15, second=0, microsecond=0)
    if now_est >= target:
        target += timedelta(days=1)
    return (target - now_est).total_seconds()


async def _build_daily_report() -> str:
    from memory.trade_journal import get_conn, put_conn
    import psycopg2.extras

    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE closed_at::date = CURRENT_DATE) AS today_trades,
                    COUNT(*) FILTER (WHERE closed_at::date = CURRENT_DATE AND pnl_usd > 0) AS today_wins,
                    COALESCE(ROUND(SUM(pnl_usd) FILTER (WHERE closed_at::date = CURRENT_DATE)::numeric, 2), 0) AS today_pnl,
                    COUNT(*) FILTER (WHERE status = 'OPEN') AS open_positions
                FROM trades
            """)
            row = dict(cur.fetchone())
    finally:
        put_conn(conn)

    total = row["today_trades"] or 0
    wins = row["today_wins"] or 0
    pnl = float(row["today_pnl"] or 0)
    open_pos = row["open_positions"] or 0
    win_rate = round(wins / total * 100, 1) if total > 0 else 0
    sign = "+" if pnl >= 0 else ""

    html = f"""
    <html><body style="font-family:monospace;background:#07090f;color:#e2e8f0;padding:24px">
    <h2 style="color:#00d084">SIGMA Daily Report — {datetime.now(EST).strftime('%Y-%m-%d')}</h2>
    <table style="border-collapse:collapse;width:400px">
      <tr><td style="padding:8px;color:#94a3b8">Trades Today</td><td style="padding:8px"><b>{total}</b></td></tr>
      <tr><td style="padding:8px;color:#94a3b8">Win Rate</td><td style="padding:8px"><b>{win_rate}%</b></td></tr>
      <tr><td style="padding:8px;color:#94a3b8">Net P&amp;L</td>
          <td style="padding:8px;color:{'#00d084' if pnl >= 0 else '#ff4d4d'}"><b>{sign}${pnl:.2f}</b></td></tr>
      <tr><td style="padding:8px;color:#94a3b8">Open Positions</td><td style="padding:8px"><b>{open_pos}</b></td></tr>
    </table>
    <p style="color:#475569;font-size:12px;margin-top:24px">SIGMA — Paper Trading Mode</p>
    </body></html>
    """
    return html


async def run_daily_scheduler():
    """Long-running coroutine. Waits until 4:15 PM EST, sends digest, repeats."""
    from notifications.service import notify_daily_digest

    while True:
        wait = _seconds_until_next_digest()
        logger.info(f"Daily digest scheduled in {wait/3600:.1f}h")
        await asyncio.sleep(wait)

        # Skip weekends
        now_est = datetime.now(EST)
        if now_est.weekday() >= 5:
            await asyncio.sleep(60)
            continue

        try:
            report = await _build_daily_report()
            notify_daily_digest(report)
            logger.info("Daily digest sent")
        except Exception as e:
            logger.error(f"Daily digest error: {e}")

        await asyncio.sleep(60)  # prevent double-fire in same minute
