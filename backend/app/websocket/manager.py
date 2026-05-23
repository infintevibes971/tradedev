import logging

from fastapi import WebSocket

from app.chain.messages import Message

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and broadcasts TradeChain messages to the UI."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.append(websocket)
        logger.info(f"WS client connected ({len(self._connections)} total)")

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.remove(websocket)
        logger.info(f"WS client disconnected ({len(self._connections)} total)")

    async def broadcast_message(self, message: Message) -> None:
        data = message.model_dump(mode="json")
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.remove(ws)

    @property
    def client_count(self) -> int:
        return len(self._connections)
