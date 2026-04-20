import asyncio
import logging
from typing import Callable
from signals.schemas import SignalEvent

logger = logging.getLogger(__name__)


class StreamConsumer:
    """
    Reads SignalEvents from an asyncio.Queue and triggers the Strategy Agent.
    Replaces Redis Streams — no external dependency needed.
    """

    def __init__(self, queue: asyncio.Queue, handler: Callable):
        self._queue = queue
        self._handler = handler
        self._running = False

    async def start(self):
        self._running = True
        logger.info("Signal consumer started — listening on in-memory queue")

        while self._running:
            try:
                # Wait up to 1 second for a signal
                signal: SignalEvent = await asyncio.wait_for(
                    self._queue.get(), timeout=1.0
                )
                try:
                    await self._handler(signal)
                except Exception as e:
                    logger.error(f"Handler error for {signal.symbol}: {e}")
                finally:
                    self._queue.task_done()

            except asyncio.TimeoutError:
                continue  # no signal yet, keep waiting
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Consumer error: {e}")
                await asyncio.sleep(1)

    def stop(self):
        self._running = False
