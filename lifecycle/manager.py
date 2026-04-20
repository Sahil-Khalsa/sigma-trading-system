import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from agents.strategy.state import TradeThesis
from agents.risk.checker import RiskAgent
from execution.alpaca_client import (
    get_account, get_positions, place_market_order, close_position, get_order_status
)
from memory.trade_journal import save_trade, close_trade, get_open_positions
import notifications.service as notif

logger = logging.getLogger(__name__)

risk_agent = RiskAgent()

_FILL_POLL_INTERVAL = 1   # seconds between fill status checks
_FILL_TIMEOUT = 15        # seconds before giving up on fill confirmation
_ORDER_MAX_RETRIES = 3


async def _place_order_with_retry(
    symbol: str, qty: float, side: str, client_order_id: str
) -> dict:
    last_err: Optional[Exception] = None
    for attempt in range(_ORDER_MAX_RETRIES):
        try:
            return await place_market_order(symbol, qty, side, client_order_id)
        except Exception as e:
            last_err = e
            logger.warning(f"Order attempt {attempt + 1} failed for {symbol}: {e}")
            if attempt < _ORDER_MAX_RETRIES - 1:
                await asyncio.sleep(2 ** attempt)
    raise last_err


async def _wait_for_fill(order_id: str) -> Optional[dict]:
    for _ in range(_FILL_TIMEOUT):
        try:
            status = await get_order_status(order_id)
            if status["status"] == "filled":
                return status
        except Exception as e:
            logger.warning(f"Fill poll error for {order_id}: {e}")
        await asyncio.sleep(_FILL_POLL_INTERVAL)
    return None


class TradeLifecycleManager:
    """
    Orchestrates the full trade lifecycle:
    thesis → risk check → execute → track → close
    """

    async def handle_thesis(self, thesis: TradeThesis, signal_id: int):
        """Called when Strategy Agent produces a TRADE decision."""
        account = await get_account()
        open_positions = await get_open_positions()
        daily_pnl_pct = account["daily_pl_pct"]

        # Risk check
        risk_result = await risk_agent.check(
            thesis=thesis,
            portfolio_value=account["portfolio_value"],
            open_positions=open_positions,
            daily_pnl_pct=daily_pnl_pct,
        )

        if not risk_result.approved:
            logger.warning(f"Trade BLOCKED: {thesis.symbol} — {risk_result.reason}")
            await save_trade(
                thesis=thesis,
                signal_id=signal_id,
                risk_check_result="BLOCKED",
                risk_check_reason=risk_result.reason,
            )
            await notif.notify_trade_blocked(thesis.symbol, risk_result.reason)
            return

        # Calculate quantity
        portfolio_value = account["portfolio_value"]
        position_value = portfolio_value * thesis.proposed_size_pct
        qty = round(position_value / thesis.entry_price, 2)

        if qty < 1:
            logger.warning(f"Quantity too small ({qty}) for {thesis.symbol} — skipping execution")
            await save_trade(
                thesis=thesis,
                signal_id=signal_id,
                risk_check_result="BLOCKED",
                risk_check_reason=f"Calculated quantity {qty} < 1 share",
            )
            return

        # Execute with retry
        side = "buy" if thesis.direction == "LONG" else "sell"
        try:
            order = await _place_order_with_retry(
                symbol=thesis.symbol,
                qty=qty,
                side=side,
                client_order_id=f"sigma_{thesis.symbol}_{int(datetime.now().timestamp())}",
            )
        except Exception as e:
            logger.error(f"Order execution failed for {thesis.symbol} after retries: {e}")
            await save_trade(
                thesis=thesis,
                signal_id=signal_id,
                risk_check_result="BLOCKED",
                risk_check_reason=f"Order placement failed: {e}",
            )
            return

        # Wait for fill confirmation
        fill = await _wait_for_fill(order["order_id"])
        if fill:
            filled_price = fill.get("filled_avg_price") or thesis.entry_price
            filled_qty = fill.get("filled_qty", qty)
            logger.info(
                f"Order filled: {thesis.symbol} {thesis.direction} x{filled_qty} @ {filled_price}"
            )
        else:
            logger.warning(
                f"Fill not confirmed within {_FILL_TIMEOUT}s for {thesis.symbol} "
                f"order {order['order_id']} — proceeding with submitted price"
            )

        logger.info(f"Trade APPROVED and executed: {thesis.symbol} {thesis.direction} x{qty}")
        await notif.notify_trade_executed(
            symbol=thesis.symbol, direction=thesis.direction, qty=qty,
            entry=thesis.entry_price, target=thesis.target_price,
            stop=thesis.stop_price, confidence=thesis.confidence,
        )

        # Save to journal
        trade_id = await save_trade(
            thesis=thesis,
            signal_id=signal_id,
            risk_check_result="APPROVED",
            risk_check_reason=risk_result.reason,
            entry_order_id=order["order_id"],
            quantity=qty,
        )

        logger.info(f"Trade saved to journal: id={trade_id}")
        return trade_id

    async def check_exits(self):
        """
        Called periodically to check if any open position has hit
        its stop-loss or take-profit target.
        """
        open_positions = await get_open_positions()
        if not open_positions:
            return

        live_positions = await get_positions()
        live_map = {p["symbol"]: p for p in live_positions}

        for trade in open_positions:
            symbol = trade["symbol"]
            if symbol not in live_map:
                continue

            current_price = float(live_map[symbol]["current_price"])
            direction = trade["direction"]
            stop = float(trade["stop_price"])
            target = float(trade["target_price"])

            exit_reason = None
            if direction == "LONG":
                if current_price <= stop:
                    exit_reason = "stop_loss"
                elif current_price >= target:
                    exit_reason = "take_profit"
            else:
                if current_price >= stop:
                    exit_reason = "stop_loss"
                elif current_price <= target:
                    exit_reason = "take_profit"

            if exit_reason:
                logger.info(f"Exiting {symbol} — reason: {exit_reason} @ {current_price}")
                await close_position(symbol)
                await close_trade(
                    trade_id=trade["id"],
                    exit_price=current_price,
                    exit_reason=exit_reason,
                )
                entry = float(trade.get("entry_price") or current_price)
                direction = trade["direction"]
                pnl_usd = (current_price - entry) * (1 if direction == "LONG" else -1)
                pnl_pct = pnl_usd / entry if entry else 0
                await notif.notify_position_closed(
                    symbol=symbol, direction=direction,
                    pnl_usd=pnl_usd, pnl_pct=pnl_pct,
                    exit_reason=exit_reason,
                )
