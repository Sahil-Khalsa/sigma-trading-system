"""
Strategy Agent tools.
Each tool returns structured data — the agent reasons over structure, not free text.
All tools are deterministic given the same inputs.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict

import httpx
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_alpaca_data = StockHistoricalDataClient(
    api_key=settings.alpaca_api_key,
    secret_key=settings.alpaca_secret_key,
)


async def get_recent_news(symbol: str, hours_back: int = 4) -> Dict[str, Any]:
    """Fetch recent news for a symbol via Polygon."""
    try:
        since = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        url = "https://api.polygon.io/v2/reference/news"
        params = {
            "ticker": symbol,
            "published_utc.gte": since,
            "order": "desc",
            "limit": 5,
            "apiKey": settings.polygon_api_key,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        articles = []
        for item in data.get("results", []):
            articles.append({
                "headline": item.get("title", ""),
                "source": item.get("publisher", {}).get("name", ""),
                "published": item.get("published_utc", ""),
                "summary": item.get("description", "")[:200],
                "url": item.get("article_url", ""),
            })

        return {"symbol": symbol, "articles": articles, "count": len(articles)}

    except Exception as e:
        logger.error(f"get_recent_news error for {symbol}: {e}")
        return {"symbol": symbol, "articles": [], "error": str(e)}


async def get_signal_history(
    symbol: str, signal_type: str, lookback_days: int = 90
) -> Dict[str, Any]:
    """Look up historical win rate for this signal/symbol combo from DB."""
    try:
        from memory.trade_journal import get_signal_stats
        stats = await get_signal_stats(symbol, signal_type)
        if not stats:
            return {
                "symbol": symbol,
                "signal_type": signal_type,
                "message": "No historical data yet",
                "win_rate": None,
                "sample_size": 0,
            }
        return {
            "symbol": symbol,
            "signal_type": signal_type,
            "win_rate": round(stats["win_rate"], 2),
            "avg_pnl_pct": round(stats["avg_pnl_pct"], 3),
            "avg_hold_minutes": round(stats["avg_hold_minutes"], 1),
            "sample_size": stats["total_trades"],
        }
    except Exception as e:
        logger.error(f"get_signal_history error: {e}")
        return {"symbol": symbol, "signal_type": signal_type, "error": str(e)}


async def get_price_context(symbol: str, bars: int = 10) -> Dict[str, Any]:
    """Fetch recent OHLCV bars to give the agent price context."""
    try:
        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=bars * 2)

        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Minute,
            start=start,
            end=end,
            limit=bars,
        )
        bars_df = _alpaca_data.get_stock_bars(request).df

        if bars_df.empty:
            return {"symbol": symbol, "bars": [], "message": "No data"}

        bars_list = []
        for _, row in bars_df.tail(bars).iterrows():
            bars_list.append({
                "close": round(float(row["close"]), 2),
                "volume": int(row["volume"]),
                "vwap": round(float(row.get("vwap", 0)), 2),
            })

        close_prices = [b["close"] for b in bars_list]
        return {
            "symbol": symbol,
            "current_price": close_prices[-1],
            "price_5bar_ago": close_prices[-5] if len(close_prices) >= 5 else None,
            "price_change_pct": round(
                (close_prices[-1] - close_prices[0]) / close_prices[0] * 100, 2
            ),
            "recent_bars": bars_list[-5:],
        }
    except Exception as e:
        logger.error(f"get_price_context error for {symbol}: {e}")
        return {"symbol": symbol, "error": str(e)}


async def get_earnings_calendar(symbol: str, days_ahead: int = 14) -> Dict[str, Any]:
    """Estimate next earnings from last SEC filing date (quarterly cycle ~91 days)."""
    try:
        url = "https://api.polygon.io/vX/reference/financials"
        params = {
            "ticker": symbol,
            "limit": 1,
            "sort": "filing_date",
            "order": "desc",
            "apiKey": settings.polygon_api_key,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            data = resp.json()

        results = data.get("results", [])
        if not results:
            return {"symbol": symbol, "next_earnings": "unknown", "days_until": None, "caution": False}

        last_filing = results[0].get("filing_date", "")
        if not last_filing:
            return {"symbol": symbol, "next_earnings": "unknown", "days_until": None, "caution": False}

        last_date = datetime.fromisoformat(last_filing).date()
        estimated_next = last_date + timedelta(days=91)
        today = datetime.now(timezone.utc).date()
        days_until = (estimated_next - today).days

        return {
            "symbol": symbol,
            "last_filing_date": last_filing,
            "estimated_next_earnings": estimated_next.isoformat(),
            "days_until_estimated": days_until,
            "within_window": days_until <= days_ahead,
            "caution": days_until <= days_ahead,
        }
    except Exception as e:
        logger.error(f"get_earnings_calendar error: {e}")
        return {"symbol": symbol, "error": str(e), "next_earnings": "unknown", "caution": False}


async def get_market_context(symbol: str) -> Dict[str, Any]:
    """Fetch macro sentiment: Fear & Greed index + SPY momentum as market backdrop."""
    result: Dict[str, Any] = {"symbol": symbol}
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            # Fear & Greed (alternative.me — free, no auth)
            fg_resp = await client.get("https://api.alternative.me/fng/?limit=1")
            fg_data = fg_resp.json().get("data", [{}])[0]
            result["fear_greed_value"] = int(fg_data.get("value", 50))
            result["fear_greed_label"] = fg_data.get("value_classification", "Neutral")
    except Exception as e:
        result["fear_greed_value"] = 50
        result["fear_greed_label"] = "Unavailable"
        result["fear_greed_error"] = str(e)

    try:
        # SPY 1-day momentum as market direction proxy
        spy_req = StockBarsRequest(
            symbol_or_symbols="SPY",
            timeframe=TimeFrame.Day,
            start=datetime.now(timezone.utc) - timedelta(days=5),
            end=datetime.now(timezone.utc),
            limit=3,
        )
        spy_df = _alpaca_data.get_stock_bars(spy_req).df
        if not spy_df.empty:
            closes = spy_df["close"].values
            spy_1d_pct = round((closes[-1] - closes[-2]) / closes[-2] * 100, 2) if len(closes) >= 2 else 0
            result["spy_1d_pct"] = spy_1d_pct
            result["market_trend"] = "bullish" if spy_1d_pct > 0.3 else "bearish" if spy_1d_pct < -0.3 else "neutral"
        else:
            result["market_trend"] = "unknown"
    except Exception as e:
        result["market_trend"] = "unknown"
        result["spy_error"] = str(e)

    fg = result.get("fear_greed_value", 50)
    result["recommendation"] = (
        "favorable — market fear creates oversold opportunities" if fg < 35
        else "cautious — extreme greed, elevated reversal risk" if fg > 75
        else "neutral market sentiment"
    )
    return result


async def get_portfolio_exposure(symbol: str) -> Dict[str, Any]:
    """Get current portfolio exposure to avoid over-concentration."""
    try:
        from memory.trade_journal import get_open_positions
        positions = await get_open_positions()
        open_symbols = [p["symbol"] for p in positions]
        already_in_position = symbol in open_symbols

        return {
            "symbol": symbol,
            "already_in_position": already_in_position,
            "total_open_positions": len(positions),
            "open_symbols": open_symbols,
        }
    except Exception as e:
        logger.error(f"get_portfolio_exposure error: {e}")
        return {"symbol": symbol, "error": str(e)}


# Tool registry — maps tool name to async function
TOOL_REGISTRY = {
    "get_recent_news":       get_recent_news,
    "get_signal_history":    get_signal_history,
    "get_price_context":     get_price_context,
    "get_earnings_calendar": get_earnings_calendar,
    "get_portfolio_exposure": get_portfolio_exposure,
    "get_market_context":    get_market_context,
}

# Expected types for each tool's parameters (used for coercion/validation)
_TOOL_SCHEMAS: Dict[str, Dict[str, type]] = {
    "get_recent_news":       {"symbol": str, "hours_back": int},
    "get_signal_history":    {"symbol": str, "signal_type": str, "lookback_days": int},
    "get_price_context":     {"symbol": str, "bars": int},
    "get_earnings_calendar": {"symbol": str, "days_ahead": int},
    "get_portfolio_exposure": {"symbol": str},
    "get_market_context":    {"symbol": str},
}


async def execute_tool(tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
    if tool_name not in TOOL_REGISTRY:
        return {"error": f"Unknown tool: {tool_name}"}

    schema = _TOOL_SCHEMAS.get(tool_name, {})
    coerced: Dict[str, Any] = {}
    for key, val in tool_input.items():
        if key in schema:
            try:
                coerced[key] = schema[key](val)
            except (ValueError, TypeError) as e:
                return {"error": f"Invalid parameter '{key}' for {tool_name}: {e}"}
        else:
            coerced[key] = val

    fn = TOOL_REGISTRY[tool_name]
    return await fn(**coerced)
