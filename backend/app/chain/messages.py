from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class MessageType(str, Enum):
    TRADE_REQUEST = "trade.request"
    TRADE_EXECUTED = "trade.executed"
    TRADE_REJECTED = "trade.rejected"
    RISK_ALERT = "risk.alert"
    CAPITAL_REQUEST = "capital.request"
    CAPITAL_RESPONSE = "capital.response"
    STATUS_REPORT = "status.report"
    ERROR_REPORT = "error.report"
    AGENT_CHAT = "agent.chat"
    SYSTEM_COMMAND = "system.command"
    WEEKLY_REPORT = "report.weekly"


class Priority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class Message(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    type: MessageType
    sender_id: str
    sender_role: str = ""
    target_id: str | None = None
    priority: Priority = Priority.NORMAL
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def topic(self) -> str:
        return self.type.value.split(".")[0]

    @property
    def is_broadcast(self) -> bool:
        return self.target_id is None


class TradeRequest(Message):
    type: MessageType = MessageType.TRADE_REQUEST

    @property
    def symbol(self) -> str:
        return self.payload.get("symbol", "")

    @property
    def side(self) -> str:
        return self.payload.get("side", "")

    @property
    def quantity(self) -> float:
        return float(self.payload.get("quantity", 0))

    @property
    def reason(self) -> str:
        return self.payload.get("reason", "")


class TradeExecuted(Message):
    type: MessageType = MessageType.TRADE_EXECUTED


class RiskAlert(Message):
    type: MessageType = MessageType.RISK_ALERT
    priority: Priority = Priority.HIGH


class ErrorReport(Message):
    type: MessageType = MessageType.ERROR_REPORT
    priority: Priority = Priority.HIGH
