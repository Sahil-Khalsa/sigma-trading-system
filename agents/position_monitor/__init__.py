import logging
from datetime import datetime, timezone

from execution.alpaca_client import get_positions, close_position
from memory.trade_journal import get_open_positions, close_trade

logger = logging.getLogger(__name__)

MAX_HOLD_HOURS = 8


class PositionMonitor:
    """
    Enhanced position monitoring: trailing stops and time-based exits.
    Runs alongside the basic stop/target check in TradeLifecycleManager.
    """

    def __init__(self, trailing_stop_pct: float = 0.005):
        self._trailing_stop_pct = trailing_stop_pct
        # symbol → best price seen since entry (high for LONG, low for SHORT)
        self._watermarks: dict = {}

    async def update(self):
        open_positions = await get_open_positions()
        if not open_positions:
            return

        live_positions = await get_positions()
        live_map = {p["symbol"]: p for p in live_positions}
        now = datetime.now(timezone.utc)

        for trade in open_positions:
            symbol = trade["symbol"]
            if symbol not in live_map:
                continue

            current_price = float(live_map[symbol]["current_price"])
            direction = trade["direction"]
            trade_id = trade["id"]

            opened_at = trade["opened_at"]
            if opened_at.tzinfo is None:
                opened_at = opened_at.replace(tzinfo=timezone.utc)

            # Time-based exit
            hold_hours = (now - opened_at).total_seconds() / 3600
            if hold_hours > MAX_HOLD_HOURS:
                logger.info(f"Time exit: {symbol} held {hold_hours:.1f}h > {MAX_HOLD_HOURS}h")
                try:
                    await close_position(symbol)
                    await close_trade(trade_id, current_price, "max_hold_time_exceeded")
                except Exception as e:
                    logger.error(f"Time exit failed for {symbol}: {e}")
                self._watermarks.pop(symbol, None)
                continue

            # Trailing stop
            try:
                if direction == "LONG":
                    hwm = self._watermarks.get(symbol, current_price)
                    if current_price > hwm:
                        self._watermarks[symbol] = current_price
                        hwm = current_price
                    trailing_stop = hwm * (1 - self._trailing_stop_pct)
                    if current_price <= trailing_stop:
                        logger.info(f"Trailing stop: {symbol} @ {current_price} (hwm={hwm:.2f})")
                        await close_position(symbol)
                        await close_trade(trade_id, current_price, "trailing_stop")
                        self._watermarks.pop(symbol, None)

                elif direction == "SHORT":
                    lwm = self._watermarks.get(symbol, current_price)
                    if current_price < lwm:
                        self._watermarks[symbol] = current_price
                        lwm = current_price
                    trailing_stop = lwm * (1 + self._trailing_stop_pct)
                    if current_price >= trailing_stop:
                        logger.info(f"Trailing stop (short): {symbol} @ {current_price} (lwm={lwm:.2f})")
                        await close_position(symbol)
                        await close_trade(trade_id, current_price, "trailing_stop")
                        self._watermarks.pop(symbol, None)

            except Exception as e:
                logger.error(f"Trailing stop check failed for {symbol}: {e}")
