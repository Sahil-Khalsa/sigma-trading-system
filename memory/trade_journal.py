import json
import logging
from datetime import datetime, timezone
from typing import Optional

import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_pool: Optional[ThreadedConnectionPool] = None


def get_pool() -> ThreadedConnectionPool:
    global _pool
    if _pool is None:
        _pool = ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=settings.database_url,
        )
    return _pool


def get_conn():
    return get_pool().getconn()


def put_conn(conn):
    get_pool().putconn(conn)


async def save_signal(signal) -> int:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO signals (symbol, signal_type, value, price, context, fired_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    signal.symbol,
                    signal.signal_type.value,
                    signal.value,
                    signal.price,
                    json.dumps(signal.context),
                    signal.fired_at,
                ),
            )
            signal_id = cur.fetchone()[0]
            conn.commit()
            return signal_id
    finally:
        put_conn(conn)


async def save_trade(
    thesis,
    signal_id: int,
    risk_check_result: str,
    risk_check_reason: str,
    entry_order_id: Optional[str] = None,
    quantity: Optional[float] = None,
) -> int:
    conn = get_conn()
    try:
        steps_json = [
            {
                "iteration": s.iteration,
                "tool_name": s.tool_name,
                "tool_input": s.tool_input,
                "tool_result": s.tool_result,
                "reasoning": s.reasoning,
            }
            for s in thesis.investigation_steps
        ]
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO trades (
                    symbol, direction, status,
                    entry_price, size_pct, quantity, entry_order_id, opened_at,
                    signal_id, thesis, investigation_steps, evidence_refs,
                    confidence, model_version,
                    risk_check_result, risk_check_reason,
                    stop_price, target_price
                )
                VALUES (%s,%s,%s, %s,%s,%s,%s,%s, %s,%s,%s,%s, %s,%s, %s,%s, %s,%s)
                RETURNING id
                """,
                (
                    thesis.symbol, thesis.direction, "OPEN",
                    thesis.entry_price, thesis.proposed_size_pct,
                    quantity, entry_order_id, datetime.now(timezone.utc),
                    signal_id, thesis.thesis,
                    json.dumps(steps_json),
                    json.dumps(thesis.evidence_refs),
                    thesis.confidence, "claude-sonnet-4-6",
                    risk_check_result, risk_check_reason,
                    thesis.stop_price, thesis.target_price,
                ),
            )
            trade_id = cur.fetchone()[0]
            conn.commit()
            return trade_id
    finally:
        put_conn(conn)


async def close_trade(
    trade_id: int,
    exit_price: float,
    exit_reason: str,
    exit_order_id: Optional[str] = None,
):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM trades WHERE id = %s", (trade_id,))
            trade = cur.fetchone()
            if not trade:
                logger.error(f"Trade {trade_id} not found")
                return

            entry = float(trade["entry_price"])
            direction = trade["direction"]
            if direction == "LONG":
                pnl_pct = (exit_price - entry) / entry
            else:
                pnl_pct = (entry - exit_price) / entry

            qty = float(trade["quantity"]) if trade["quantity"] else 0
            if direction == "LONG":
                pnl_usd = qty * (exit_price - entry)
            else:
                pnl_usd = qty * (entry - exit_price)

            cur.execute(
                """
                UPDATE trades
                SET status='CLOSED', exit_price=%s, exit_reason=%s,
                    exit_order_id=%s, closed_at=%s,
                    pnl_pct=%s, pnl_usd=%s
                WHERE id=%s
                """,
                (
                    exit_price, exit_reason, exit_order_id,
                    datetime.now(timezone.utc),
                    round(pnl_pct, 5), round(pnl_usd, 2),
                    trade_id,
                ),
            )
            conn.commit()

        # Update signal stats (learning loop)
        await _update_signal_stats(
            symbol=trade["symbol"],
            signal_id=trade["signal_id"],
            pnl_pct=pnl_pct,
            opened_at=trade["opened_at"],
            closed_at=datetime.now(timezone.utc),
        )
    finally:
        put_conn(conn)


async def _update_signal_stats(
    symbol: str,
    signal_id: int,
    pnl_pct: float,
    opened_at: datetime,
    closed_at: datetime,
):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # Get signal type
            cur.execute("SELECT signal_type FROM signals WHERE id=%s", (signal_id,))
            row = cur.fetchone()
            if not row:
                return
            signal_type = row["signal_type"]

            hold_minutes = (closed_at - opened_at).total_seconds() / 60
            won = 1 if pnl_pct > 0 else 0

            cur.execute(
                """
                INSERT INTO signal_stats (symbol, signal_type, total_trades, winning_trades, avg_pnl_pct, avg_hold_minutes)
                VALUES (%s, %s, 1, %s, %s, %s)
                ON CONFLICT (symbol, signal_type) DO UPDATE SET
                    total_trades = signal_stats.total_trades + 1,
                    winning_trades = signal_stats.winning_trades + EXCLUDED.winning_trades,
                    avg_pnl_pct = (signal_stats.avg_pnl_pct * signal_stats.total_trades + EXCLUDED.avg_pnl_pct)
                                  / (signal_stats.total_trades + 1),
                    avg_hold_minutes = (signal_stats.avg_hold_minutes * signal_stats.total_trades + EXCLUDED.avg_hold_minutes)
                                       / (signal_stats.total_trades + 1),
                    last_updated = NOW()
                """,
                (symbol, signal_type, won, pnl_pct, hold_minutes),
            )
            conn.commit()
    finally:
        put_conn(conn)


async def get_open_positions() -> list:
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT symbol, direction, entry_price, size_pct, stop_price, target_price, opened_at, id "
                "FROM trades WHERE status='OPEN'"
            )
            return [dict(row) for row in cur.fetchall()]
    finally:
        put_conn(conn)


def close_pool():
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None


async def save_portfolio_snapshot(account: dict):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO portfolio_snapshots (cash, total_value, daily_pnl_pct, daily_pnl_usd, snapshotted_at)
                VALUES (%s, %s, %s, %s, NOW())
                """,
                (
                    account["cash"],
                    account["portfolio_value"],
                    account["daily_pl_pct"],
                    account["daily_pl"],
                ),
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Portfolio snapshot error: {e}")
    finally:
        put_conn(conn)


async def get_portfolio_history(limit: int = 96) -> list:
    """Return the last N portfolio snapshots for the P&L chart."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT total_value, daily_pnl_usd, snapshotted_at "
                "FROM portfolio_snapshots ORDER BY snapshotted_at DESC LIMIT %s",
                (limit,),
            )
            rows = cur.fetchall()
            return [dict(r) for r in reversed(rows)]
    finally:
        put_conn(conn)


async def get_signal_stats(symbol: str, signal_type: str) -> Optional[dict]:
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT * FROM signal_stats WHERE symbol=%s AND signal_type=%s",
                (symbol, signal_type),
            )
            row = cur.fetchone()
            if not row:
                return None
            d = dict(row)
            d["win_rate"] = d["winning_trades"] / d["total_trades"] if d["total_trades"] > 0 else 0
            return d
    finally:
        put_conn(conn)
