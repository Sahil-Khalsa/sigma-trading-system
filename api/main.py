import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.middleware import RateLimitMiddleware
from api.routes.trades import router as trades_router
from api.routes.portfolio import router as portfolio_router
from api.routes.ws import router as ws_router
from api.routes.test import router as test_router
from api.routes.backtest import router as backtest_router
from api.routes.analytics import router as analytics_router
from api.routes.notifications import router as notifications_router

app = FastAPI(
    title="SIGMA API",
    version="1.0.0",
    description="Multi-Agent AI Trading System — Real-time signal detection, autonomous agent reasoning, and risk management.",
)

_default_origins = [
    "http://localhost:5173",
    "http://localhost:80",
    "http://localhost",
]
_extra = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
_origin_regex = os.getenv("CORS_ORIGIN_REGEX") or r"https://.*\.vercel\.app"

app.add_middleware(RateLimitMiddleware, calls=120, period=60)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_default_origins + _extra,
    allow_origin_regex=_origin_regex,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(trades_router)
app.include_router(portfolio_router)
app.include_router(ws_router)
app.include_router(test_router)
app.include_router(backtest_router)
app.include_router(analytics_router)
app.include_router(notifications_router)


@app.get("/health")
async def health():
    from memory.trade_journal import get_pool
    try:
        pool = get_pool()
        conn = pool.getconn()
        pool.putconn(conn)
        db_ok = True
    except Exception:
        db_ok = False
    return {"status": "ok", "db": "connected" if db_ok else "error"}
