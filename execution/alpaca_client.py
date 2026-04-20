import logging
from typing import Optional

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderType
from alpaca.trading.models import Order

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_trading_client = TradingClient(
    api_key=settings.alpaca_api_key,
    secret_key=settings.alpaca_secret_key,
    paper=True,  # always paper — enforced here, not just in policy
)


async def get_account() -> dict:
    account = _trading_client.get_account()
    return {
        "portfolio_value": float(account.portfolio_value),
        "cash": float(account.cash),
        "buying_power": float(account.buying_power),
        "daily_pl": float(account.equity) - float(account.last_equity),
        "daily_pl_pct": (
            (float(account.equity) - float(account.last_equity))
            / float(account.last_equity)
            if float(account.last_equity) > 0
            else 0
        ),
    }


async def get_positions() -> list:
    positions = _trading_client.get_all_positions()
    return [
        {
            "symbol": p.symbol,
            "qty": float(p.qty),
            "avg_entry_price": float(p.avg_entry_price),
            "current_price": float(p.current_price),
            "unrealized_pl": float(p.unrealized_pl),
            "unrealized_plpc": float(p.unrealized_plpc),
            "side": p.side.value,
        }
        for p in positions
    ]


async def place_market_order(
    symbol: str,
    qty: float,
    side: str,  # "buy" | "sell"
    client_order_id: Optional[str] = None,
) -> dict:
    order_side = OrderSide.BUY if side == "buy" else OrderSide.SELL

    request = MarketOrderRequest(
        symbol=symbol,
        qty=qty,
        side=order_side,
        time_in_force=TimeInForce.DAY,
        client_order_id=client_order_id,
    )

    order: Order = _trading_client.submit_order(request)
    logger.info(f"Order submitted: {side} {qty} {symbol} | id={order.id}")

    return {
        "order_id": str(order.id),
        "symbol": order.symbol,
        "qty": float(order.qty),
        "side": order.side.value,
        "status": order.status.value,
        "submitted_at": str(order.submitted_at),
    }


async def close_position(symbol: str) -> dict:
    result = _trading_client.close_position(symbol)
    logger.info(f"Closed position: {symbol}")
    return {"symbol": symbol, "status": "closed", "order_id": str(result.id)}


async def get_order_status(order_id: str) -> dict:
    order = _trading_client.get_order_by_id(order_id)
    return {
        "order_id": str(order.id),
        "status": order.status.value,
        "filled_qty": float(order.filled_qty) if order.filled_qty else 0,
        "filled_avg_price": float(order.filled_avg_price) if order.filled_avg_price else None,
    }
