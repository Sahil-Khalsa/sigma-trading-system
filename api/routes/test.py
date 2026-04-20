"""
Test mode — fires a simulated signal through the full agent pipeline.
Only available in development.
"""

from fastapi import APIRouter
from datetime import datetime, timezone
from signals.schemas import SignalEvent, SignalType

router = APIRouter(prefix="/test", tags=["test"])

# Will be set by main.py after system is created
_signal_handler = None


def register_handler(handler):
    global _signal_handler
    _signal_handler = handler


@router.post("/fire-signal")
async def fire_test_signal(
    symbol: str = "AAPL",
    signal_type: str = "volume_surge",
    value: float = 3.2,
    price: float = 182.50,
):
    if _signal_handler is None:
        return {"error": "System not ready"}

    signal = SignalEvent(
        symbol=symbol,
        signal_type=SignalType(signal_type),
        value=value,
        price=price,
        context={
            "volume_ratio": value,
            "rsi": 58.4,
            "vwap_dev": 0.8,
        },
        fired_at=datetime.now(timezone.utc),
    )

    # Run in background so API returns immediately
    import asyncio
    asyncio.create_task(_signal_handler(signal))

    return {
        "status": "fired",
        "symbol": symbol,
        "signal_type": signal_type,
        "price": price,
    }
