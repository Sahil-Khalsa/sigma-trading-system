"""
SIGMA — Real-Time Multi-Agent Trading System
Entry point: starts all components and runs the event loop.
"""

import asyncio
import logging
import sys

import uvicorn

from config import get_settings
from data.alpaca_ws import AlpacaFeed
from signals.detector import SignalDetector
from signals.schemas import SignalEvent
from streams.publisher import StreamPublisher
from streams.consumer import StreamConsumer
from agents.strategy.agent import StrategyAgent
from lifecycle.manager import TradeLifecycleManager
from memory.trade_journal import save_signal, close_pool, save_portfolio_snapshot, get_open_positions
from agents.position_monitor import PositionMonitor
from api.main import app
from api.ws_manager import ws_manager
from api.routes.test import register_handler as register_test_handler
import notifications.service as notif
from notifications.scheduler import run_daily_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)
settings = get_settings()


class SigmaSystem:
    def __init__(self):
        self._signal_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self.feed = AlpacaFeed()
        self.detector = SignalDetector()
        self.publisher = StreamPublisher(queue=self._signal_queue)
        self.strategy_agent = StrategyAgent()
        self.lifecycle = TradeLifecycleManager()
        self.position_monitor = PositionMonitor()
        self._running = False

    async def _on_bar(self, symbol: str, bar: dict, buffer):
        signals = await self.detector.on_bar(symbol, bar, buffer)
        for signal in signals:
            logger.info(f"Signal fired: {signal.symbol} {signal.signal_type.value} value={signal.value}")
            self.publisher.publish_signal(signal)
            await notif.notify_signal_fired(
                signal.symbol, signal.signal_type.value, signal.value, signal.price
            )
            await ws_manager.broadcast("signal_fired", {
                "symbol": signal.symbol,
                "signal_type": signal.signal_type.value,
                "value": signal.value,
                "price": signal.price,
                "context": signal.context,
                "fired_at": signal.fired_at.isoformat(),
            })

    async def _on_signal(self, signal: SignalEvent):
        logger.info(f"Investigating: {signal.symbol} {signal.signal_type.value}")

        await ws_manager.broadcast("investigation_started", {
            "symbol": signal.symbol,
            "signal_type": signal.signal_type.value,
            "price": signal.price,
        })

        signal_id = await save_signal(signal)
        final_state = await self.strategy_agent.investigate(signal)

        # Broadcast full investigation trace
        steps = [
            {
                "iteration": s.iteration,
                "tool_name": s.tool_name,
                "tool_input": s.tool_input,
                "reasoning": s.reasoning,
            }
            for s in final_state.get("steps", [])
        ]

        if final_state["decision"] == "trade" and final_state.get("thesis"):
            thesis = final_state["thesis"]
            await ws_manager.broadcast("trade_decision", {
                "symbol": thesis.symbol,
                "direction": thesis.direction,
                "confidence": thesis.confidence,
                "thesis": thesis.thesis,
                "entry_price": thesis.entry_price,
                "target_price": thesis.target_price,
                "stop_price": thesis.stop_price,
                "steps": steps,
            })
            await self.lifecycle.handle_thesis(thesis=thesis, signal_id=signal_id)

        else:
            pass_decision = final_state.get("pass_decision")
            reason = pass_decision.reason if pass_decision else "unknown"
            await ws_manager.broadcast("trade_passed", {
                "symbol": signal.symbol,
                "reason": reason,
                "steps": steps,
            })
            await notif.notify_agent_passed(signal.symbol, reason)
            logger.info(f"Agent passed on {signal.symbol}: {reason}")

    async def _snapshot_loop(self):
        """Save portfolio snapshot every 15 minutes for the P&L chart."""
        while self._running:
            try:
                from execution.alpaca_client import get_account
                account = await get_account()
                await save_portfolio_snapshot(account)
            except Exception as e:
                logger.error(f"Snapshot error: {e}")
            await asyncio.sleep(900)  # 15 minutes

    async def _exit_monitor(self):
        while self._running:
            try:
                await self.lifecycle.check_exits()
                await self.position_monitor.update()
            except Exception as e:
                logger.error(f"Exit monitor error: {e}")
            await asyncio.sleep(settings.exit_monitor_interval_seconds)

    async def _start_api(self):
        config = uvicorn.Config(
            app=app,
            host="0.0.0.0",
            port=8000,
            log_level="warning",
        )
        server = uvicorn.Server(config)
        await server.serve()

    async def start(self):
        self._running = True

        notif.configure(
            telegram_token=settings.telegram_bot_token or None,
            telegram_chat_id=settings.telegram_chat_id or None,
            smtp_host=settings.smtp_host or None,
            smtp_port=settings.smtp_port,
            smtp_user=settings.smtp_user or None,
            smtp_password=settings.smtp_password or None,
            notification_email=settings.notification_email or None,
        )

        logger.info("=" * 60)
        logger.info("SIGMA starting up")
        logger.info(f"Watchlist: {settings.watchlist_symbols}")
        logger.info(f"Paper trading: YES (enforced)")
        logger.info(f"Dashboard API: http://localhost:8000")
        logger.info("=" * 60)

        self.feed.register_handler(self._on_bar)
        register_test_handler(self._on_signal)

        consumer = StreamConsumer(
            queue=self._signal_queue,
            handler=self._on_signal,
        )

        # Log recovered open positions on startup
        try:
            open_pos = await get_open_positions()
            if open_pos:
                logger.info(f"Recovered {len(open_pos)} open position(s) from DB: {[p['symbol'] for p in open_pos]}")
        except Exception:
            pass

        await asyncio.gather(
            self.feed.start(),
            consumer.start(),
            self._exit_monitor(),
            self._snapshot_loop(),
            self._start_api(),
            run_daily_scheduler(),
        )

    async def stop(self):
        self._running = False
        await self.feed.stop()
        close_pool()
        logger.info("SIGMA stopped")


async def main():
    system = SigmaSystem()
    try:
        await system.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await system.stop()


if __name__ == "__main__":
    asyncio.run(main())
