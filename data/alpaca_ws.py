import asyncio
import logging
from collections import deque
from datetime import datetime
from typing import Callable, Dict, List

import pandas as pd
from alpaca.data.live import StockDataStream
from alpaca.data.models import Bar

from config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


class PriceBuffer:
    """
    Maintains a rolling window of recent bars per symbol.
    Used by the Signal Detector to compute indicators.
    """

    def __init__(self, window: int = 50):
        self.window = window
        # symbol -> deque of Bar dicts
        self._bars: Dict[str, deque] = {}

    def add(self, symbol: str, bar: dict):
        if symbol not in self._bars:
            self._bars[symbol] = deque(maxlen=self.window)
        self._bars[symbol].append(bar)

    def get_df(self, symbol: str) -> pd.DataFrame:
        if symbol not in self._bars or len(self._bars[symbol]) < 2:
            return pd.DataFrame()
        return pd.DataFrame(list(self._bars[symbol]))

    def ready(self, symbol: str, min_bars: int = 20) -> bool:
        return symbol in self._bars and len(self._bars[symbol]) >= min_bars


class AlpacaFeed:
    """
    Subscribes to Alpaca real-time bar data for the watchlist.
    Calls registered handlers on each new bar.
    """

    def __init__(self):
        self.symbols: List[str] = settings.watchlist_symbols
        self.price_buffer = PriceBuffer(window=50)
        self._bar_handlers: List[Callable] = []
        self._stream = StockDataStream(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
        )

    def register_handler(self, handler: Callable):
        """Register a callback that receives (symbol, bar_dict) on each bar."""
        self._bar_handlers.append(handler)

    async def _on_bar(self, bar: Bar):
        symbol = bar.symbol
        bar_dict = {
            "symbol": symbol,
            "open": float(bar.open),
            "high": float(bar.high),
            "low": float(bar.low),
            "close": float(bar.close),
            "volume": float(bar.volume),
            "vwap": float(bar.vwap) if bar.vwap else None,
            "timestamp": bar.timestamp,
        }

        self.price_buffer.add(symbol, bar_dict)
        logger.debug(f"Bar: {symbol} close={bar_dict['close']} vol={bar_dict['volume']}")

        for handler in self._bar_handlers:
            try:
                await handler(symbol, bar_dict, self.price_buffer)
            except Exception as e:
                logger.error(f"Bar handler error for {symbol}: {e}")

    async def start(self):
        logger.info(f"Starting Alpaca feed for: {self.symbols}")
        self._stream.subscribe_bars(self._on_bar, *self.symbols)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._stream.run)

    async def stop(self):
        self._stream.stop()
