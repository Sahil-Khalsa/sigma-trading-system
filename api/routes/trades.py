from fastapi import APIRouter, HTTPException
import psycopg2.extras
from memory.trade_journal import get_conn, put_conn

router = APIRouter(prefix="/trades", tags=["trades"])


@router.get("/")
async def list_trades(status: str = None, limit: int = 20):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if status:
                cur.execute(
                    "SELECT * FROM trades WHERE status=%s ORDER BY created_at DESC LIMIT %s",
                    (status, limit),
                )
            else:
                cur.execute(
                    "SELECT * FROM trades ORDER BY created_at DESC LIMIT %s", (limit,)
                )
            return cur.fetchall()
    finally:
        put_conn(conn)


@router.get("/{trade_id}")
async def get_trade(trade_id: int):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM trades WHERE id=%s", (trade_id,))
            trade = cur.fetchone()
            if not trade:
                raise HTTPException(status_code=404, detail="Trade not found")
            return trade
    finally:
        put_conn(conn)


@router.get("/{trade_id}/investigation")
async def get_investigation(trade_id: int):
    """Returns the full agent reasoning trace for a trade."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT symbol, direction, thesis, investigation_steps, "
                "evidence_refs, confidence, risk_check_result, risk_check_reason "
                "FROM trades WHERE id=%s",
                (trade_id,),
            )
            trade = cur.fetchone()
            if not trade:
                raise HTTPException(status_code=404, detail="Trade not found")
            return trade
    finally:
        put_conn(conn)
