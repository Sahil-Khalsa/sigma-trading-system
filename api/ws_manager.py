"""
WebSocket connection manager.
Broadcasts real-time events to all connected dashboard clients.
"""

import json
import logging
from typing import Any, Dict, List
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WSManager:
    def __init__(self):
        self._connections: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.append(ws)
        logger.info(f"Dashboard connected. Total: {len(self._connections)}")

    def disconnect(self, ws: WebSocket):
        self._connections.remove(ws)
        logger.info(f"Dashboard disconnected. Total: {len(self._connections)}")

    async def broadcast(self, event_type: str, data: Dict[str, Any]):
        if not self._connections:
            return
        message = json.dumps({"type": event_type, "data": data})
        dead = []
        for ws in self._connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.remove(ws)


# Global instance — imported by main.py and agents
ws_manager = WSManager()
