from fastapi import APIRouter, Query
from execution.alpaca_client import get_account, get_positions
from memory.trade_journal import get_conn, put_conn, get_portfolio_history
import psycopg2.extras

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("/state")
async def get_portfolio_state():
    account = await get_account()
    positions = await get_positions()
    return {"account": account, "positions": positions}


@router.get("/history")
async def get_history(limit: int = Query(default=96, le=500)):
    snapshots = await get_portfolio_history(limit)
    return [
        {
            "time": s["snapshotted_at"].isoformat(),
            "value": s["total_value"],
            "daily_pnl": s["daily_pnl_usd"],
        }
        for s in snapshots
    ]


@router.get("/performance")
async def get_performance():
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    COUNT(*) AS total_trades,
                    COUNT(*) FILTER (WHERE pnl_pct > 0) AS winning_trades,
                    ROUND(AVG(pnl_pct)::numeric, 4) AS avg_pnl_pct,
                    ROUND(SUM(pnl_usd)::numeric, 2) AS total_pnl_usd,
                    ROUND(MAX(pnl_pct)::numeric, 4) AS best_trade_pct,
                    ROUND(MIN(pnl_pct)::numeric, 4) AS worst_trade_pct
                FROM trades
                WHERE status = 'CLOSED'
            """)
            summary = cur.fetchone()

            cur.execute("""
                SELECT symbol, signal_type, total_trades,
                       ROUND((winning_trades::float / NULLIF(total_trades,0))::numeric, 2) AS win_rate,
                       ROUND(avg_pnl_pct::numeric, 4) AS avg_pnl_pct
                FROM signal_stats
                ORDER BY total_trades DESC
                LIMIT 10
            """)
            signal_breakdown = cur.fetchall()

            return {
                "summary": summary,
                "signal_breakdown": signal_breakdown,
            }
    finally:
        put_conn(conn)
