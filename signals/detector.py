import logging
from datetime import datetime, timezone
from typing import List, Optional

import pandas as pd
import ta

from signals.schemas import SignalEvent, SignalType
from data.alpaca_ws import PriceBuffer

logger = logging.getLogger(__name__)

# Thresholds
VOLUME_SURGE_MULTIPLIER  = 2.5     # current volume > 2.5x 20-bar average
RSI_OVERSOLD_THRESHOLD   = 32.0
RSI_OVERBOUGHT_THRESHOLD = 72.0
VWAP_BREAKOUT_PCT        = 0.015   # price deviates > 1.5% from VWAP
MOMENTUM_LOOKBACK        = 5       # bars for momentum calculation
MOMENTUM_THRESHOLD_PCT   = 0.02    # 2% price move in MOMENTUM_LOOKBACK bars
PRICE_BREAKOUT_LOOKBACK  = 20      # bars for high/low breakout
BB_BANDWIDTH_SQUEEZE     = 0.03    # Bollinger Band width < 3% = squeeze
MIN_BARS_REQUIRED        = 26      # enough for MACD (26-period)


class SignalDetector:
    """
    Rule-based signal detection. No LLM.
    Runs on every new bar and publishes SignalEvents when conditions are met.
    """

    def __init__(self):
        # Cooldown: prevent firing the same signal for same symbol within N bars
        self._last_signal: dict = {}  # (symbol, signal_type) -> bar count
        self._bar_count: dict = {}    # symbol -> total bar count
        self.cooldown_bars = 5

    async def on_bar(
        self,
        symbol: str,
        bar: dict,
        buffer: PriceBuffer,
    ) -> List[SignalEvent]:
        """
        Called on every new bar. Returns list of fired signals (empty if none).
        """
        self._bar_count[symbol] = self._bar_count.get(symbol, 0) + 1

        if not buffer.ready(symbol, MIN_BARS_REQUIRED):
            return []

        df = buffer.get_df(symbol)
        signals = []

        # --- Volume Surge ---
        vol_signal = self._check_volume_surge(symbol, df)
        if vol_signal:
            signals.append(vol_signal)

        # --- RSI ---
        rsi_signal = self._check_rsi(symbol, df)
        if rsi_signal:
            signals.append(rsi_signal)

        # --- VWAP Breakout ---
        vwap_signal = self._check_vwap_breakout(symbol, df)
        if vwap_signal:
            signals.append(vwap_signal)

        # --- Momentum Spike ---
        mom_signal = self._check_momentum_spike(symbol, df)
        if mom_signal:
            signals.append(mom_signal)

        # --- Price Breakout (20-bar high/low) ---
        breakout_signal = self._check_price_breakout(symbol, df)
        if breakout_signal:
            signals.append(breakout_signal)

        # --- MACD Crossover ---
        macd_signal = self._check_macd(symbol, df)
        if macd_signal:
            signals.append(macd_signal)

        # --- Bollinger Band Squeeze ---
        bb_signal = self._check_bb_squeeze(symbol, df)
        if bb_signal:
            signals.append(bb_signal)

        return signals

    def _check_volume_surge(self, symbol: str, df: pd.DataFrame) -> Optional[SignalEvent]:
        if len(df) < 20:
            return None

        current_vol = df["volume"].iloc[-1]
        avg_vol = df["volume"].iloc[-21:-1].mean()  # 20-bar average excluding current

        if avg_vol == 0:
            return None

        ratio = current_vol / avg_vol
        if ratio < VOLUME_SURGE_MULTIPLIER:
            return None

        if self._on_cooldown(symbol, SignalType.VOLUME_SURGE):
            return None

        self._set_cooldown(symbol, SignalType.VOLUME_SURGE)

        rsi = self._compute_rsi(df)
        return SignalEvent(
            symbol=symbol,
            signal_type=SignalType.VOLUME_SURGE,
            value=round(ratio, 2),
            price=df["close"].iloc[-1],
            context={
                "volume_ratio": round(ratio, 2),
                "current_volume": int(current_vol),
                "avg_volume": int(avg_vol),
                "rsi": round(rsi, 1) if rsi else None,
            },
            fired_at=datetime.now(timezone.utc),
        )

    def _check_rsi(self, symbol: str, df: pd.DataFrame) -> Optional[SignalEvent]:
        rsi = self._compute_rsi(df)
        if rsi is None:
            return None

        if rsi <= RSI_OVERSOLD_THRESHOLD:
            signal_type = SignalType.RSI_OVERSOLD
        elif rsi >= RSI_OVERBOUGHT_THRESHOLD:
            signal_type = SignalType.RSI_OVERBOUGHT
        else:
            return None

        if self._on_cooldown(symbol, signal_type):
            return None

        self._set_cooldown(symbol, signal_type)

        return SignalEvent(
            symbol=symbol,
            signal_type=signal_type,
            value=round(rsi, 2),
            price=df["close"].iloc[-1],
            context={
                "rsi": round(rsi, 1),
                "close": df["close"].iloc[-1],
            },
            fired_at=datetime.now(timezone.utc),
        )

    def _check_vwap_breakout(self, symbol: str, df: pd.DataFrame) -> Optional[SignalEvent]:
        if "vwap" not in df.columns:
            return None

        latest = df.iloc[-1]
        vwap = latest.get("vwap")
        close = latest["close"]

        if not vwap or vwap == 0:
            return None

        deviation = (close - vwap) / vwap

        if abs(deviation) < VWAP_BREAKOUT_PCT:
            return None

        if self._on_cooldown(symbol, SignalType.VWAP_BREAKOUT):
            return None

        self._set_cooldown(symbol, SignalType.VWAP_BREAKOUT)

        return SignalEvent(
            symbol=symbol,
            signal_type=SignalType.VWAP_BREAKOUT,
            value=round(deviation * 100, 2),  # as percentage
            price=close,
            context={
                "vwap": round(vwap, 2),
                "close": round(close, 2),
                "deviation_pct": round(deviation * 100, 2),
            },
            fired_at=datetime.now(timezone.utc),
        )

    def _check_momentum_spike(self, symbol: str, df: pd.DataFrame) -> Optional[SignalEvent]:
        if len(df) < MOMENTUM_LOOKBACK + 1:
            return None

        close_now  = df["close"].iloc[-1]
        close_then = df["close"].iloc[-MOMENTUM_LOOKBACK - 1]
        if close_then == 0:
            return None

        change_pct = (close_now - close_then) / close_then
        if abs(change_pct) < MOMENTUM_THRESHOLD_PCT:
            return None

        if self._on_cooldown(symbol, SignalType.MOMENTUM_SPIKE):
            return None
        self._set_cooldown(symbol, SignalType.MOMENTUM_SPIKE)

        return SignalEvent(
            symbol=symbol,
            signal_type=SignalType.MOMENTUM_SPIKE,
            value=round(change_pct * 100, 2),
            price=close_now,
            context={
                "change_pct": round(change_pct * 100, 2),
                "lookback_bars": MOMENTUM_LOOKBACK,
                "direction": "up" if change_pct > 0 else "down",
            },
            fired_at=datetime.now(timezone.utc),
        )

    def _check_price_breakout(self, symbol: str, df: pd.DataFrame) -> Optional[SignalEvent]:
        if len(df) < PRICE_BREAKOUT_LOOKBACK + 1:
            return None

        close    = df["close"].iloc[-1]
        window   = df["close"].iloc[-PRICE_BREAKOUT_LOOKBACK - 1:-1]
        high_20  = window.max()
        low_20   = window.min()

        if close > high_20:
            direction = "up"
        elif close < low_20:
            direction = "down"
        else:
            return None

        if self._on_cooldown(symbol, SignalType.PRICE_BREAKOUT):
            return None
        self._set_cooldown(symbol, SignalType.PRICE_BREAKOUT)

        return SignalEvent(
            symbol=symbol,
            signal_type=SignalType.PRICE_BREAKOUT,
            value=round(close, 2),
            price=close,
            context={
                "direction": direction,
                "breakout_level": round(high_20 if direction == "up" else low_20, 2),
                "lookback_bars": PRICE_BREAKOUT_LOOKBACK,
            },
            fired_at=datetime.now(timezone.utc),
        )

    def _check_macd(self, symbol: str, df: pd.DataFrame) -> Optional[SignalEvent]:
        if len(df) < 26:
            return None

        macd_ind  = ta.trend.MACD(df["close"], window_slow=26, window_fast=12, window_sign=9)
        macd_line = macd_ind.macd()
        signal_line = macd_ind.macd_signal()

        if macd_line.isna().iloc[-1] or signal_line.isna().iloc[-1]:
            return None

        prev_diff = macd_line.iloc[-2] - signal_line.iloc[-2]
        curr_diff = macd_line.iloc[-1] - signal_line.iloc[-1]

        # Bullish crossover: MACD crossed above signal
        if prev_diff < 0 and curr_diff > 0:
            signal_type = SignalType.MACD_BULLISH
        # Bearish crossover: MACD crossed below signal
        elif prev_diff > 0 and curr_diff < 0:
            signal_type = SignalType.MACD_BEARISH
        else:
            return None

        if self._on_cooldown(symbol, signal_type):
            return None
        self._set_cooldown(symbol, signal_type)

        return SignalEvent(
            symbol=symbol,
            signal_type=signal_type,
            value=round(curr_diff, 4),
            price=df["close"].iloc[-1],
            context={
                "macd": round(float(macd_line.iloc[-1]), 4),
                "signal": round(float(signal_line.iloc[-1]), 4),
                "histogram": round(curr_diff, 4),
            },
            fired_at=datetime.now(timezone.utc),
        )

    def _check_bb_squeeze(self, symbol: str, df: pd.DataFrame) -> Optional[SignalEvent]:
        """Fires when Bollinger Bands are unusually tight — volatility compression before a move."""
        if len(df) < 20:
            return None

        bb = ta.volatility.BollingerBands(df["close"], window=20, window_dev=2)
        upper = bb.bollinger_hband().iloc[-1]
        lower = bb.bollinger_lband().iloc[-1]
        mid   = bb.bollinger_mavg().iloc[-1]

        if pd.isna(upper) or pd.isna(lower) or mid == 0:
            return None

        bandwidth = (upper - lower) / mid
        if bandwidth >= BB_BANDWIDTH_SQUEEZE:
            return None

        if self._on_cooldown(symbol, SignalType.BB_SQUEEZE):
            return None
        self._set_cooldown(symbol, SignalType.BB_SQUEEZE)

        close = df["close"].iloc[-1]
        return SignalEvent(
            symbol=symbol,
            signal_type=SignalType.BB_SQUEEZE,
            value=round(bandwidth * 100, 3),
            price=close,
            context={
                "bandwidth_pct": round(bandwidth * 100, 3),
                "upper": round(upper, 2),
                "lower": round(lower, 2),
                "mid": round(mid, 2),
                "close": round(close, 2),
            },
            fired_at=datetime.now(timezone.utc),
        )

    def _compute_rsi(self, df: pd.DataFrame, period: int = 14) -> Optional[float]:
        if len(df) < period + 1:
            return None
        rsi_series = ta.momentum.RSIIndicator(df["close"], window=period).rsi()
        if rsi_series.empty or pd.isna(rsi_series.iloc[-1]):
            return None
        return float(rsi_series.iloc[-1])

    def _on_cooldown(self, symbol: str, signal_type: SignalType) -> bool:
        key = (symbol, signal_type)
        last = self._last_signal.get(key)
        current = self._bar_count.get(symbol, 0)
        if last is None:
            return False
        return (current - last) < self.cooldown_bars

    def _set_cooldown(self, symbol: str, signal_type: SignalType):
        key = (symbol, signal_type)
        self._last_signal[key] = self._bar_count.get(symbol, 0)
