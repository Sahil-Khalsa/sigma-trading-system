from fastapi import APIRouter
import psycopg2.extras
from memory.trade_journal import get_conn, put_conn

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary")
async def analytics_summary():
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE status = 'CLOSED') AS total_trades,
                    COUNT(*) FILTER (WHERE status = 'CLOSED' AND pnl_usd > 0) AS winning_trades,
                    COALESCE(ROUND(SUM(pnl_usd) FILTER (WHERE status = 'CLOSED')::numeric, 2), 0) AS total_pnl_usd,
                    COALESCE(ROUND(AVG(pnl_pct) FILTER (WHERE status = 'CLOSED' AND pnl_usd > 0)::numeric * 100, 3), 0) AS avg_win_pct,
                    COALESCE(ROUND(AVG(pnl_pct) FILTER (WHERE status = 'CLOSED' AND pnl_usd < 0)::numeric * 100, 3), 0) AS avg_loss_pct,
                    COALESCE(ROUND(AVG(confidence) FILTER (WHERE status = 'CLOSED')::numeric, 3), 0) AS avg_confidence
                FROM trades
            """)
            row = dict(cur.fetchone())
            total = row["total_trades"] or 0
            wins = row["winning_trades"] or 0
            row["win_rate_pct"] = round(wins / total * 100, 1) if total > 0 else 0
            return row
    finally:
        put_conn(conn)


@router.get("/signal-heatmap")
async def signal_heatmap():
    """Win rate matrix: each row = (symbol, signal_type) with stats."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    symbol, signal_type,
                    total_trades,
                    winning_trades,
                    ROUND(winning_trades::numeric / NULLIF(total_trades, 0) * 100, 1) AS win_rate_pct,
                    ROUND(avg_pnl_pct::numeric * 100, 3) AS avg_pnl_pct,
                    ROUND(avg_hold_minutes::numeric, 1) AS avg_hold_minutes
                FROM signal_stats
                ORDER BY symbol, signal_type
            """)
            return cur.fetchall()
    finally:
        put_conn(conn)


@router.get("/pnl-timeline")
async def pnl_timeline(limit: int = 100):
    """Per-trade P&L ordered by close time — for the distribution chart."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    id, symbol, direction,
                    entry_price, exit_price,
                    pnl_usd, pnl_pct, confidence,
                    opened_at, closed_at, exit_reason
                FROM trades
                WHERE status = 'CLOSED' AND pnl_usd IS NOT NULL
                ORDER BY closed_at ASC
                LIMIT %s
            """, (limit,))
            return cur.fetchall()
    finally:
        put_conn(conn)


@router.get("/hourly-activity")
async def hourly_activity():
    """Signal counts by hour of day (EST) over the last 30 days."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    EXTRACT(HOUR FROM fired_at AT TIME ZONE 'America/New_York')::int AS hour,
                    signal_type,
                    COUNT(*) AS count
                FROM signals
                WHERE fired_at >= NOW() - INTERVAL '30 days'
                GROUP BY hour, signal_type
                ORDER BY hour, signal_type
            """)
            return cur.fetchall()
    finally:
        put_conn(conn)


@router.get("/top-symbols")
async def top_symbols():
    """Best and worst performing symbols by total P&L."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    symbol,
                    COUNT(*) AS total_trades,
                    COUNT(*) FILTER (WHERE pnl_usd > 0) AS wins,
                    ROUND(SUM(pnl_usd)::numeric, 2) AS total_pnl_usd,
                    ROUND(AVG(pnl_usd)::numeric, 2) AS avg_pnl_usd
                FROM trades
                WHERE status = 'CLOSED' AND pnl_usd IS NOT NULL
                GROUP BY symbol
                ORDER BY total_pnl_usd DESC
                LIMIT 15
            """)
            return cur.fetchall()
    finally:
        put_conn(conn)
