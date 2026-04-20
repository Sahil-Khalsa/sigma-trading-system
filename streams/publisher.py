import asyncio
import logging
from signals.schemas import SignalEvent

logger = logging.getLogger(__name__)


class StreamPublisher:
    """
    Publishes SignalEvents to an asyncio.Queue.
    Replaces Redis Streams — no external dependency needed.
    """

    def __init__(self, queue: asyncio.Queue):
        self._queue = queue

    def publish_signal(self, signal: SignalEvent):
        try:
            self._queue.put_nowait(signal)
            logger.info(
                f"Published signal: {signal.symbol} "
                f"{signal.signal_type.value} @ {signal.price}"
            )
        except asyncio.QueueFull:
            logger.warning(
                f"Signal queue full — dropping {signal.symbol} "
                f"{signal.signal_type.value} (backpressure)"
            )

    def health_check(self) -> bool:
        return True  # always available — in-process queue
