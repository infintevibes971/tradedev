import asyncio
import logging
from collections import defaultdict
from collections.abc import Callable, Coroutine
from typing import Any

from app.chain.messages import Message

logger = logging.getLogger(__name__)

MessageHandler = Callable[[Message], Coroutine[Any, Any, None]]


class TradeChain:
    """Async pub/sub message bus for inter-agent communication.

    Agents subscribe to topics (e.g. "trade", "risk", "error").
    Messages route by topic for broadcasts, or directly by target_id.
    All messages are also forwarded to WebSocket listeners for the UI.
    """

    def __init__(self, max_history: int = 500) -> None:
        self._topic_subscribers: dict[str, dict[str, MessageHandler]] = defaultdict(dict)
        self._direct_handlers: dict[str, MessageHandler] = {}
        self._history: list[Message] = []
        self._max_history = max_history
        self._ws_callbacks: list[Callable[[Message], Coroutine[Any, Any, None]]] = []
        self._lock = asyncio.Lock()

    def subscribe(self, agent_id: str, topic: str, handler: MessageHandler) -> None:
        self._topic_subscribers[topic][agent_id] = handler
        logger.info(f"Agent {agent_id} subscribed to topic '{topic}'")

    def subscribe_direct(self, agent_id: str, handler: MessageHandler) -> None:
        self._direct_handlers[agent_id] = handler
        logger.info(f"Agent {agent_id} registered for direct messages")

    def unsubscribe(self, agent_id: str) -> None:
        for topic_subs in self._topic_subscribers.values():
            topic_subs.pop(agent_id, None)
        self._direct_handlers.pop(agent_id, None)
        logger.info(f"Agent {agent_id} unsubscribed from all topics")

    def on_ws_message(self, callback: Callable[[Message], Coroutine[Any, Any, None]]) -> None:
        self._ws_callbacks.append(callback)

    async def publish(self, message: Message) -> None:
        async with self._lock:
            self._history.append(message)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

        tasks: list[asyncio.Task] = []

        if message.target_id and message.target_id in self._direct_handlers:
            handler = self._direct_handlers[message.target_id]
            tasks.append(asyncio.create_task(self._safe_deliver(handler, message)))
        elif message.is_broadcast:
            topic = message.topic
            for agent_id, handler in self._topic_subscribers.get(topic, {}).items():
                if agent_id != message.sender_id:
                    tasks.append(asyncio.create_task(self._safe_deliver(handler, message)))

        for ws_cb in self._ws_callbacks:
            tasks.append(asyncio.create_task(self._safe_deliver(ws_cb, message)))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _safe_deliver(self, handler: MessageHandler, message: Message) -> None:
        try:
            await handler(message)
        except Exception:
            logger.exception(f"Handler failed for message {message.id} ({message.type})")

    def get_history(self, topic: str | None = None, limit: int = 50) -> list[Message]:
        msgs = self._history
        if topic:
            msgs = [m for m in msgs if m.topic == topic]
        return msgs[-limit:]

    @property
    def subscriber_count(self) -> int:
        unique = set()
        for subs in self._topic_subscribers.values():
            unique.update(subs.keys())
        unique.update(self._direct_handlers.keys())
        return len(unique)
