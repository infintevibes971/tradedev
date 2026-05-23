import asyncio
import logging
from abc import ABC, abstractmethod
from enum import Enum

from app.chain.messages import Message, MessageType, Priority
from app.chain.tradechain import TradeChain


class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class BaseAgent(ABC):
    """Base class for all TradeDev agents.

    Subclasses must implement:
        - execute(): the main work loop body (called repeatedly)
        - handle_message(): process incoming TradeChain messages
    """

    def __init__(
        self,
        agent_id: str,
        role: str,
        chain: TradeChain,
        loop_interval: float = 1.0,
    ) -> None:
        self.agent_id = agent_id
        self.role = role
        self.chain = chain
        self.loop_interval = loop_interval
        self.status = AgentStatus.IDLE
        self.logger = logging.getLogger(f"agent.{agent_id}")

        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

        self.metrics: dict = {
            "messages_sent": 0,
            "messages_received": 0,
            "errors": 0,
            "cycles": 0,
        }

    @abstractmethod
    async def execute(self) -> None:
        """One iteration of the agent's main work loop."""

    @abstractmethod
    async def handle_message(self, message: Message) -> None:
        """Process an incoming message from the TradeChain."""

    def subscribe_to(self, *topics: str) -> None:
        for topic in topics:
            self.chain.subscribe(self.agent_id, topic, self._on_message)
        self.chain.subscribe_direct(self.agent_id, self._on_message)

    async def send(
        self,
        msg_type: MessageType,
        payload: dict,
        target_id: str | None = None,
        priority: Priority = Priority.NORMAL,
    ) -> None:
        message = Message(
            type=msg_type,
            sender_id=self.agent_id,
            sender_role=self.role,
            target_id=target_id,
            priority=priority,
            payload=payload,
        )
        self.metrics["messages_sent"] += 1
        await self.chain.publish(message)

    async def _on_message(self, message: Message) -> None:
        self.metrics["messages_received"] += 1
        try:
            await self.handle_message(message)
        except Exception:
            self.metrics["errors"] += 1
            self.logger.exception(f"Error handling message {message.id}")

    async def start(self) -> None:
        if self.status == AgentStatus.RUNNING:
            return
        self._stop_event.clear()
        self.status = AgentStatus.RUNNING
        self._task = asyncio.create_task(self._run_loop(), name=f"agent-{self.agent_id}")
        self.logger.info(f"Agent {self.agent_id} ({self.role}) started")

    async def stop(self) -> None:
        self._stop_event.set()
        self.status = AgentStatus.STOPPED
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.chain.unsubscribe(self.agent_id)
        self.logger.info(f"Agent {self.agent_id} stopped")

    def pause(self) -> None:
        self.status = AgentStatus.PAUSED

    def resume(self) -> None:
        if self.status == AgentStatus.PAUSED:
            self.status = AgentStatus.RUNNING

    async def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            if self.status == AgentStatus.PAUSED:
                await asyncio.sleep(0.5)
                continue
            try:
                await self.execute()
                self.metrics["cycles"] += 1
            except Exception:
                self.metrics["errors"] += 1
                self.status = AgentStatus.ERROR
                self.logger.exception(f"Agent {self.agent_id} execution error")
                await self.send(
                    MessageType.ERROR_REPORT,
                    {
                        "agent_id": self.agent_id,
                        "error": "Execution loop failure — see logs",
                    },
                    priority=Priority.HIGH,
                )
                await asyncio.sleep(5.0)
                self.status = AgentStatus.RUNNING
            await asyncio.sleep(self.loop_interval)

    def get_status(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "role": self.role,
            "status": self.status.value,
            "metrics": self.metrics,
        }
