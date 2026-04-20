"""
Backtest engine — replays historical Alpaca bars through the signal detector
and simulates rule-based fills without calling the LLM (fast + free).
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from config import get_settings
from data.alpaca_ws import PriceBuffer
from signals.detector import SignalDetector
from signals.schemas import SignalType

logger = logging.getLogger(__name__)
settings = get_settings()

_alpaca = StockHistoricalDataClient(
    api_key=settings.alpaca_api_key,
    secret_key=settings.alpaca_secret_key,
)


@dataclass
class BacktestTrade:
    symbol: str
    direction: str
    entry_price: float
    target_price: float
    stop_price: float
    entry_time: datetime
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    exit_reason: Optional[str] = None
    pnl_pct: Optional[float] = None
    pnl_usd: Optional[float] = None  # assumes $10k per trade notional


@dataclass
class BacktestResult:
    symbol: str
    start_date: str
    end_date: str
    total_bars: int
    total_signals: int
    total_trades: int
    wins: int
    losses: int
    gross_pnl_pct: float
    trades: List[BacktestTrade] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def win_rate(self) -> float:
        return self.wins / self.total_trades if self.total_trades > 0 else 0.0

    @property
    def avg_pnl_pct(self) -> float:
        return self.gross_pnl_pct / self.total_trades if self.total_trades > 0 else 0.0

    @property
    def profit_factor(self) -> float:
        gross_win = sum(t.pnl_pct for t in self.trades if (t.pnl_pct or 0) > 0)
        gross_loss = abs(sum(t.pnl_pct for t in self.trades if (t.pnl_pct or 0) < 0))
        return round(gross_win / gross_loss, 2) if gross_loss > 0 else float("inf")

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "total_bars": self.total_bars,
            "total_signals": self.total_signals,
            "total_trades": self.total_trades,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": round(self.win_rate, 4),
            "avg_pnl_pct": round(self.avg_pnl_pct, 5),
            "gross_pnl_pct": round(self.gross_pnl_pct, 5),
            "profit_factor": self.profit_factor,
            "error": self.error,
            "trades": [
                {
                    "direction": t.direction,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "pnl_pct": round(t.pnl_pct, 5) if t.pnl_pct is not None else None,
                    "pnl_usd": round(t.pnl_usd, 2) if t.pnl_usd is not None else None,
                    "exit_reason": t.exit_reason,
                    "entry_time": t.entry_time.isoformat(),
                    "exit_time": t.exit_time.isoformat() if t.exit_time else None,
                }
                for t in self.trades
            ],
        }


# Rules: signal_type → (direction, target_pct, stop_pct)
_SIGNAL_RULES = {
    # (direction, target_pct, stop_pct)
    SignalType.RSI_OVERSOLD:   ("LONG",  0.020, 0.010),
    SignalType.RSI_OVERBOUGHT: ("SHORT", 0.020, 0.010),
    SignalType.VOLUME_SURGE:   ("LONG",  0.015, 0.008),
    SignalType.VWAP_BREAKOUT:  ("LONG",  0.018, 0.009),
    SignalType.MOMENTUM_SPIKE: ("LONG",  0.025, 0.012),
    SignalType.PRICE_BREAKOUT: ("LONG",  0.022, 0.011),
    SignalType.MACD_BULLISH:   ("LONG",  0.020, 0.010),
    SignalType.MACD_BEARISH:   ("SHORT", 0.020, 0.010),
    SignalType.BB_SQUEEZE:     ("LONG",  0.030, 0.015),
}

NOTIONAL_PER_TRADE = 10_000  # $ per simulated trade


async def run_backtest(
    symbol: str,
    start_date: str,
    end_date: str,
) -> BacktestResult:
    """
    Replay 1-min historical bars → signal detection → rule-based fills.
    Does NOT call the LLM (fast, deterministic, zero API cost).
    """
    result = BacktestResult(
        symbol=symbol, start_date=start_date, end_date=end_date,
        total_bars=0, total_signals=0, total_trades=0,
        wins=0, losses=0, gross_pnl_pct=0.0,
    )

    try:
        start_dt = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
        end_dt   = datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc)

        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Minute,
            start=start_dt,
            end=end_dt,
        )
        bars_raw = _alpaca.get_stock_bars(request)
        bars_df = bars_raw.df

        if bars_df.empty:
            result.error = "No historical data returned for this symbol/range"
            return result

        # Normalize index
        if hasattr(bars_df.index, "levels"):
            bars_df = bars_df.reset_index()
            bars_df = bars_df[bars_df["symbol"] == symbol].copy()
        else:
            bars_df = bars_df.reset_index()

        bars_df = bars_df.sort_values("timestamp").reset_index(drop=True)

    except Exception as e:
        result.error = f"Data fetch failed: {e}"
        logger.error(f"Backtest data fetch error for {symbol}: {e}")
        return result

    detector = SignalDetector()
    buffer = PriceBuffer(window=50)
    open_trade: Optional[BacktestTrade] = None

    for _, row in bars_df.iterrows():
        bar = {
            "close": float(row["close"]),
            "volume": int(row["volume"]),
            "vwap": float(row["vwap"]) if "vwap" in row and row["vwap"] else float(row["close"]),
            "timestamp": row.get("timestamp"),
        }
        bar_time = row.get("timestamp", datetime.now(timezone.utc))
        if hasattr(bar_time, "to_pydatetime"):
            bar_time = bar_time.to_pydatetime()

        buffer.add(symbol, bar)
        result.total_bars += 1

        # --- Check exits before looking for new signals ---
        if open_trade:
            price = bar["close"]
            hit_target = hit_stop = False
            if open_trade.direction == "LONG":
                hit_target = price >= open_trade.target_price
                hit_stop   = price <= open_trade.stop_price
            else:
                hit_target = price <= open_trade.target_price
                hit_stop   = price >= open_trade.stop_price

            if hit_target or hit_stop:
                _close_trade(open_trade, price, "take_profit" if hit_target else "stop_loss", bar_time, result)
                open_trade = None

        # --- Detect new signals ---
        signals = await detector.on_bar(symbol, bar, buffer)
        for sig in signals:
            result.total_signals += 1
            if open_trade:
                continue  # one position at a time

            rule = _SIGNAL_RULES.get(sig.signal_type)
            if not rule:
                continue

            direction, tgt_pct, stop_pct = rule
            price = sig.price
            if direction == "LONG":
                target = round(price * (1 + tgt_pct), 4)
                stop   = round(price * (1 - stop_pct), 4)
            else:
                target = round(price * (1 - tgt_pct), 4)
                stop   = round(price * (1 + stop_pct), 4)

            open_trade = BacktestTrade(
                symbol=symbol, direction=direction,
                entry_price=price, target_price=target, stop_price=stop,
                entry_time=bar_time,
            )
            result.total_trades += 1

    # Close any remaining open position at last bar
    if open_trade and not bars_df.empty:
        last_price = float(bars_df.iloc[-1]["close"])
        last_time_raw = bars_df.iloc[-1].get("timestamp", datetime.now(timezone.utc))
        if hasattr(last_time_raw, "to_pydatetime"):
            last_time_raw = last_time_raw.to_pydatetime()
        _close_trade(open_trade, last_price, "end_of_period", last_time_raw, result)

    return result


def _close_trade(
    trade: BacktestTrade,
    exit_price: float,
    reason: str,
    exit_time: datetime,
    result: BacktestResult,
):
    trade.exit_price = exit_price
    trade.exit_reason = reason
    trade.exit_time = exit_time

    if trade.direction == "LONG":
        trade.pnl_pct = (exit_price - trade.entry_price) / trade.entry_price
    else:
        trade.pnl_pct = (trade.entry_price - exit_price) / trade.entry_price

    trade.pnl_usd = trade.pnl_pct * NOTIONAL_PER_TRADE
    result.gross_pnl_pct += trade.pnl_pct

    if trade.pnl_pct > 0:
        result.wins += 1
    else:
        result.losses += 1

    result.trades.append(trade)
