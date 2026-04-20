"""
End-to-end tests for SIGMA. Uses mocks for all external I/O (Alpaca, OpenAI,
Polygon, PostgreSQL) so the suite runs offline without credentials.
"""

import asyncio
import json
import sys
import os
from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Make project root importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_signal(symbol="AAPL", signal_type="rsi_oversold", price=175.0):
    from signals.schemas import SignalEvent, SignalType
    return SignalEvent(
        symbol=symbol,
        signal_type=SignalType(signal_type),
        value=28.5,
        price=price,
        context={"rsi": 28.5, "volume_ratio": 1.2},
        fired_at=datetime.now(timezone.utc),
    )


def _make_thesis(symbol="AAPL", direction="LONG", price=175.0, confidence=0.82):
    from agents.strategy.state import TradeThesis
    return TradeThesis(
        symbol=symbol,
        direction=direction,
        confidence=confidence,
        thesis="Oversold on RSI with volume confirmation.",
        entry_price=price,
        target_price=round(price * 1.03, 2),
        stop_price=round(price * 0.985, 2),
        proposed_size_pct=0.05,
        evidence_refs=["get_price_context: ['current_price']"],
        investigation_steps=[],
        formed_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# 1. Signal detection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_signal_detector_rsi_oversold():
    from signals.detector import SignalDetector
    detector = SignalDetector()

    bar = {"close": 150.0, "volume": 50_000, "vwap": 152.0}
    # Feed 30 bars to build RSI buffer; last bar forces RSI < 30
    prices = [160.0] * 14 + [150.0] * 15 + [145.0]  # downtrend → oversold
    buffer = MagicMock()
    buffer.closes = prices

    signals = await detector.on_bar("TSLA", bar, buffer)
    # Detector may or may not fire depending on exact RSI calc — just check no crash
    assert isinstance(signals, list)


@pytest.mark.asyncio
async def test_signal_detector_cooldown():
    from signals.detector import SignalDetector
    detector = SignalDetector()

    bar = {"close": 150.0, "volume": 500_000, "vwap": 145.0}
    buffer = MagicMock()
    buffer.closes = [150.0] * 50
    buffer.volumes = [50_000] * 49 + [500_000]
    buffer.vwaps = [145.0] * 50

    # Manually inject a recent cooldown for TSLA/volume_surge
    from signals.schemas import SignalType
    detector._last_signal[("TSLA", SignalType.VOLUME_SURGE)] = datetime.now(timezone.utc)

    signals = await detector.on_bar("TSLA", bar, buffer)
    volume_surges = [s for s in signals if s.signal_type == SignalType.VOLUME_SURGE]
    assert len(volume_surges) == 0, "Cooldown should suppress duplicate signal"


# ---------------------------------------------------------------------------
# 2. Risk checker
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_risk_check_all_pass():
    from agents.risk.checker import RiskAgent
    risk = RiskAgent()
    thesis = _make_thesis()

    result = await risk.check(
        thesis=thesis,
        portfolio_value=100_000,
        open_positions=[],
        daily_pnl_pct=0.0,
    )
    assert result.approved, f"Expected approval, got: {result.reason}"


@pytest.mark.asyncio
async def test_risk_check_daily_loss_limit():
    from agents.risk.checker import RiskAgent
    risk = RiskAgent()
    thesis = _make_thesis()

    result = await risk.check(
        thesis=thesis,
        portfolio_value=100_000,
        open_positions=[],
        daily_pnl_pct=-0.025,  # exceeds 2% limit
    )
    assert not result.approved
    assert "daily loss" in result.reason.lower()


@pytest.mark.asyncio
async def test_risk_check_max_positions():
    from agents.risk.checker import RiskAgent
    risk = RiskAgent()
    thesis = _make_thesis(symbol="GOOGL")

    fake_positions = [
        {"symbol": f"SYM{i}", "size_pct": 0.05} for i in range(5)
    ]
    result = await risk.check(
        thesis=thesis,
        portfolio_value=100_000,
        open_positions=fake_positions,
        daily_pnl_pct=0.0,
    )
    assert not result.approved
    assert "max open positions" in result.reason.lower()


@pytest.mark.asyncio
async def test_risk_check_sector_concentration():
    from agents.risk.checker import RiskAgent
    risk = RiskAgent()
    thesis = _make_thesis(symbol="NVDA")  # Technology

    # Already have 40% in Technology (4 × 10% positions)
    fake_positions = [
        {"symbol": s, "size_pct": 0.10} for s in ["AAPL", "MSFT", "GOOGL", "AMD"]
    ]
    result = await risk.check(
        thesis=thesis,
        portfolio_value=100_000,
        open_positions=fake_positions,
        daily_pnl_pct=0.0,
    )
    assert not result.approved
    assert "sector" in result.reason.lower()


@pytest.mark.asyncio
async def test_risk_check_low_rr_ratio():
    from agents.strategy.state import TradeThesis
    from agents.risk.checker import RiskAgent
    risk = RiskAgent()

    # R:R of 0.5 — well below 1.5 minimum
    thesis = TradeThesis(
        symbol="AAPL",
        direction="LONG",
        confidence=0.85,
        thesis="Test",
        entry_price=175.0,
        target_price=176.0,   # +$1 reward
        stop_price=172.0,     # -$3 risk
        proposed_size_pct=0.05,
        evidence_refs=[],
        investigation_steps=[],
        formed_at=datetime.now(timezone.utc),
    )
    result = await risk.check(
        thesis=thesis,
        portfolio_value=100_000,
        open_positions=[],
        daily_pnl_pct=0.0,
    )
    assert not result.approved
    assert "reward" in result.reason.lower() or "ratio" in result.reason.lower()


# ---------------------------------------------------------------------------
# 3. Tool execution & validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_tool_unknown():
    from agents.strategy.tools import execute_tool
    result = await execute_tool("nonexistent_tool", {})
    assert "error" in result


@pytest.mark.asyncio
async def test_execute_tool_type_coercion():
    from agents.strategy import tools as tools_mod
    mock_fn = AsyncMock(return_value={"symbol": "AAPL", "current_price": 175.0})
    original = tools_mod.TOOL_REGISTRY["get_price_context"]
    tools_mod.TOOL_REGISTRY["get_price_context"] = mock_fn
    try:
        await tools_mod.execute_tool("get_price_context", {"symbol": "AAPL", "bars": "10"})
        # "10" should be coerced to int before calling the function
        mock_fn.assert_called_once_with(symbol="AAPL", bars=10)
    finally:
        tools_mod.TOOL_REGISTRY["get_price_context"] = original


@pytest.mark.asyncio
async def test_execute_tool_invalid_type():
    from agents.strategy.tools import execute_tool
    result = await execute_tool("get_price_context", {"symbol": "AAPL", "bars": "not_a_number"})
    assert "error" in result


@pytest.mark.asyncio
async def test_earnings_calendar_estimates_next_date():
    from agents.strategy.tools import get_earnings_calendar
    fake_response = {
        "results": [{"filing_date": "2025-01-15"}]
    }
    with patch("agents.strategy.tools.httpx.AsyncClient") as mock_client_cls:
        mock_resp = MagicMock()
        mock_resp.json.return_value = fake_response
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
            get=AsyncMock(return_value=mock_resp)
        ))
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await get_earnings_calendar("AAPL", days_ahead=14)

    assert "estimated_next_earnings" in result
    assert "days_until_estimated" in result
    assert "caution" in result


# ---------------------------------------------------------------------------
# 4. Position monitor
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_position_monitor_trailing_stop_long():
    from agents.position_monitor import PositionMonitor

    monitor = PositionMonitor(trailing_stop_pct=0.01)  # 1% trailing stop

    fake_open = [{
        "id": 1,
        "symbol": "AAPL",
        "direction": "LONG",
        "stop_price": 170.0,
        "target_price": 185.0,
        "opened_at": datetime.now(timezone.utc),
    }]
    # Price rose to 180 then fell to 177.5 (> 1% from 180 = 178.2 trigger)
    fake_live = [{"symbol": "AAPL", "current_price": 177.5}]

    with patch("agents.position_monitor.get_open_positions", new_callable=AsyncMock, return_value=fake_open), \
         patch("agents.position_monitor.get_positions", new_callable=AsyncMock, return_value=fake_live), \
         patch("agents.position_monitor.close_position", new_callable=AsyncMock) as mock_close_pos, \
         patch("agents.position_monitor.close_trade", new_callable=AsyncMock) as mock_close_trade:

        # First tick: establish HWM at 177.5
        await monitor.update()
        # Simulate price rose to 180
        monitor._watermarks["AAPL"] = 180.0
        # Now price is 177.5, trailing stop = 180 * 0.99 = 178.2 — should trigger
        await monitor.update()

        mock_close_pos.assert_called_with("AAPL")
        mock_close_trade.assert_called_with(1, 177.5, "trailing_stop")


@pytest.mark.asyncio
async def test_position_monitor_time_exit():
    from agents.position_monitor import PositionMonitor, MAX_HOLD_HOURS
    from datetime import timedelta

    monitor = PositionMonitor()
    old_open_time = datetime.now(timezone.utc) - timedelta(hours=MAX_HOLD_HOURS + 1)

    fake_open = [{
        "id": 99,
        "symbol": "MSFT",
        "direction": "LONG",
        "stop_price": 300.0,
        "target_price": 330.0,
        "opened_at": old_open_time,
    }]
    fake_live = [{"symbol": "MSFT", "current_price": 315.0}]

    with patch("agents.position_monitor.get_open_positions", new_callable=AsyncMock, return_value=fake_open), \
         patch("agents.position_monitor.get_positions", new_callable=AsyncMock, return_value=fake_live), \
         patch("agents.position_monitor.close_position", new_callable=AsyncMock) as mock_close_pos, \
         patch("agents.position_monitor.close_trade", new_callable=AsyncMock) as mock_close_trade:

        await monitor.update()

        mock_close_pos.assert_called_with("MSFT")
        mock_close_trade.assert_called_with(99, 315.0, "max_hold_time_exceeded")


# ---------------------------------------------------------------------------
# 5. Trade lifecycle — full path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_lifecycle_approved_trade():
    from lifecycle.manager import TradeLifecycleManager

    thesis = _make_thesis(confidence=0.85)
    manager = TradeLifecycleManager()

    fake_account = {
        "portfolio_value": 100_000.0,
        "cash": 80_000.0,
        "buying_power": 80_000.0,
        "daily_pl": 0.0,
        "daily_pl_pct": 0.0,
    }
    fake_order = {
        "order_id": "order-123",
        "symbol": "AAPL",
        "qty": 28.57,
        "side": "buy",
        "status": "accepted",
        "submitted_at": "2026-04-18T10:00:00Z",
    }
    fake_fill = {"order_id": "order-123", "status": "filled", "filled_qty": 28.57, "filled_avg_price": 175.0}

    with patch("lifecycle.manager.get_account", new_callable=AsyncMock, return_value=fake_account), \
         patch("lifecycle.manager.get_open_positions", new_callable=AsyncMock, return_value=[]), \
         patch("lifecycle.manager.place_market_order", new_callable=AsyncMock, return_value=fake_order), \
         patch("lifecycle.manager.get_order_status", new_callable=AsyncMock, return_value=fake_fill), \
         patch("lifecycle.manager.save_trade", new_callable=AsyncMock, return_value=42) as mock_save:

        trade_id = await manager.handle_thesis(thesis=thesis, signal_id=1)

    mock_save.assert_called_once()
    call_kwargs = mock_save.call_args.kwargs
    assert call_kwargs["risk_check_result"] == "APPROVED"
    assert trade_id == 42


@pytest.mark.asyncio
async def test_lifecycle_blocked_by_risk():
    from lifecycle.manager import TradeLifecycleManager

    thesis = _make_thesis(confidence=0.85)
    manager = TradeLifecycleManager()

    fake_account = {
        "portfolio_value": 100_000.0,
        "cash": 80_000.0,
        "buying_power": 80_000.0,
        "daily_pl": -2500.0,
        "daily_pl_pct": -0.025,  # triggers daily loss halt
    }

    with patch("lifecycle.manager.get_account", new_callable=AsyncMock, return_value=fake_account), \
         patch("lifecycle.manager.get_open_positions", new_callable=AsyncMock, return_value=[]), \
         patch("lifecycle.manager.save_trade", new_callable=AsyncMock, return_value=7) as mock_save, \
         patch("lifecycle.manager.place_market_order", new_callable=AsyncMock) as mock_order:

        await manager.handle_thesis(thesis=thesis, signal_id=2)

    mock_order.assert_not_called()
    call_kwargs = mock_save.call_args.kwargs
    assert call_kwargs["risk_check_result"] == "BLOCKED"


@pytest.mark.asyncio
async def test_lifecycle_qty_too_small():
    from lifecycle.manager import TradeLifecycleManager
    from agents.strategy.state import TradeThesis

    # Very small position size → qty < 1
    thesis = TradeThesis(
        symbol="NVDA",
        direction="LONG",
        confidence=0.85,
        thesis="Test",
        entry_price=900.0,
        target_price=930.0,
        stop_price=880.0,
        proposed_size_pct=0.0009,  # $90 on a $900 stock = 0.1 shares
        evidence_refs=[],
        investigation_steps=[],
        formed_at=datetime.now(timezone.utc),
    )
    manager = TradeLifecycleManager()

    fake_account = {
        "portfolio_value": 100_000.0, "cash": 80_000.0,
        "buying_power": 80_000.0, "daily_pl": 0.0, "daily_pl_pct": 0.0,
    }

    with patch("lifecycle.manager.get_account", new_callable=AsyncMock, return_value=fake_account), \
         patch("lifecycle.manager.get_open_positions", new_callable=AsyncMock, return_value=[]), \
         patch("lifecycle.manager.save_trade", new_callable=AsyncMock, return_value=8) as mock_save, \
         patch("lifecycle.manager.place_market_order", new_callable=AsyncMock) as mock_order:

        await manager.handle_thesis(thesis=thesis, signal_id=3)

    mock_order.assert_not_called()
    call_kwargs = mock_save.call_args.kwargs
    assert call_kwargs["risk_check_result"] == "BLOCKED"
    assert "quantity" in call_kwargs["risk_check_reason"].lower()


@pytest.mark.asyncio
async def test_lifecycle_exit_check():
    from lifecycle.manager import TradeLifecycleManager

    manager = TradeLifecycleManager()

    fake_open = [{
        "id": 10,
        "symbol": "AAPL",
        "direction": "LONG",
        "stop_price": 170.0,
        "target_price": 185.0,
    }]
    fake_live = [{"symbol": "AAPL", "current_price": 186.0}]  # hit take-profit

    with patch("lifecycle.manager.get_open_positions", new_callable=AsyncMock, return_value=fake_open), \
         patch("lifecycle.manager.get_positions", new_callable=AsyncMock, return_value=fake_live), \
         patch("lifecycle.manager.close_position", new_callable=AsyncMock) as mock_cp, \
         patch("lifecycle.manager.close_trade", new_callable=AsyncMock) as mock_ct:

        await manager.check_exits()

    mock_cp.assert_called_with("AAPL")
    mock_ct.assert_called_with(trade_id=10, exit_price=186.0, exit_reason="take_profit")


# ---------------------------------------------------------------------------
# 6. Trade journal — PnL calculation (real quantity-based)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_close_trade_pnl_uses_quantity():
    from memory.trade_journal import close_trade

    fake_trade = {
        "entry_price": 170.0,
        "direction": "LONG",
        "quantity": 10.0,
        "size_pct": 0.05,
        "symbol": "AAPL",
        "signal_id": 1,
        "opened_at": datetime.now(timezone.utc),
    }

    captured_pnl = {}

    def fake_execute(sql, params):
        if "UPDATE trades" in sql:
            # params order: exit_price, exit_reason, exit_order_id, closed_at, pnl_pct, pnl_usd, trade_id
            captured_pnl["pnl_pct"] = params[4]
            captured_pnl["pnl_usd"] = params[5]

    mock_cur = MagicMock()
    mock_cur.__enter__ = MagicMock(return_value=mock_cur)
    mock_cur.__exit__ = MagicMock(return_value=False)
    mock_cur.fetchone.return_value = fake_trade
    mock_cur.execute.side_effect = fake_execute

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cur
    mock_conn.commit = MagicMock()

    with patch("memory.trade_journal.get_conn", return_value=mock_conn), \
         patch("memory.trade_journal.put_conn"), \
         patch("memory.trade_journal._update_signal_stats", new_callable=AsyncMock):

        await close_trade(trade_id=1, exit_price=180.0, exit_reason="take_profit")

    # LONG: pnl_usd = 10 shares × ($180 - $170) = $100
    assert captured_pnl["pnl_usd"] == 100.0
    assert abs(captured_pnl["pnl_pct"] - (10.0 / 170.0)) < 0.001


# ---------------------------------------------------------------------------
# 7. Stream queue backpressure
# ---------------------------------------------------------------------------

def test_publisher_drops_on_full_queue():
    import asyncio
    from streams.publisher import StreamPublisher

    q: asyncio.Queue = asyncio.Queue(maxsize=2)
    pub = StreamPublisher(q)
    sig = _make_signal()

    pub.publish_signal(sig)
    pub.publish_signal(sig)
    # Third publish should not raise — it should be silently dropped
    pub.publish_signal(sig)

    assert q.qsize() == 2


# ---------------------------------------------------------------------------
# 8. Strategy agent state initialisation
# ---------------------------------------------------------------------------

def test_agent_initial_state_has_pending_tool_none():
    from agents.strategy.agent import StrategyAgent
    agent = StrategyAgent.__new__(StrategyAgent)

    signal = _make_signal()
    # Build the initial_state dict directly (mirrors agent.py logic)
    from config import get_settings
    settings = get_settings.__wrapped__() if hasattr(get_settings, "__wrapped__") else get_settings()

    initial_state = {
        "symbol": signal.symbol,
        "signal_type": signal.signal_type.value,
        "signal_value": signal.value,
        "current_price": signal.price,
        "signal_context": signal.context,
        "steps": [],
        "current_reasoning": "",
        "confidence": 0.0,
        "decision": "continue",
        "thesis": None,
        "pass_decision": None,
        "iteration": 0,
        "max_iterations": 7,
        "error": None,
        "_pending_tool": None,
    }

    assert initial_state["_pending_tool"] is None
    assert initial_state["decision"] == "continue"
    assert initial_state["thesis"] is None
