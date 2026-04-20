from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class SignalType(str, Enum):
    VOLUME_SURGE    = "volume_surge"
    RSI_OVERSOLD    = "rsi_oversold"
    RSI_OVERBOUGHT  = "rsi_overbought"
    VWAP_BREAKOUT   = "vwap_breakout"
    PRICE_BREAKOUT  = "price_breakout"
    MOMENTUM_SPIKE  = "momentum_spike"
    MACD_BULLISH    = "macd_bullish"
    MACD_BEARISH    = "macd_bearish"
    BB_SQUEEZE      = "bb_squeeze"


class SignalEvent(BaseModel):
    symbol: str
    signal_type: SignalType
    value: float                     # the numeric value that triggered it
    price: float                     # current price when signal fired
    context: Dict[str, Any]          # rsi, volume_ratio, vwap_dev, etc.
    fired_at: datetime

    def to_stream_dict(self) -> Dict[str, str]:
        """Serialize for Redis Streams (all values must be strings)."""
        return {
            "symbol": self.symbol,
            "signal_type": self.signal_type.value,
            "value": str(self.value),
            "price": str(self.price),
            "context": self.model_dump_json(),
            "fired_at": self.fired_at.isoformat(),
        }

    @classmethod
    def from_stream_dict(cls, data: Dict[str, str]) -> "SignalEvent":
        import json
        ctx = json.loads(data["context"])
        return cls(
            symbol=data["symbol"],
            signal_type=SignalType(data["signal_type"]),
            value=float(data["value"]),
            price=float(data["price"]),
            context=ctx.get("context", {}),
            fired_at=datetime.fromisoformat(data["fired_at"]),
        )
