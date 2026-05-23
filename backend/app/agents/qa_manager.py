import logging
from collections import defaultdict
from datetime import datetime, timezone

from app.agents.base import BaseAgent
from app.chain.messages import Message, MessageType, Priority
from app.chain.tradechain import TradeChain

logger = logging.getLogger(__name__)


class ErrorRecord:
    __slots__ = ("agent_id", "error_type", "details", "timestamp", "resolved")

    def __init__(self, agent_id: str, error_type: str, details: str, timestamp: datetime):
        self.agent_id = agent_id
        self.error_type = error_type
        self.details = details
        self.timestamp = timestamp
        self.resolved = False


class QAManager(BaseAgent):
    """Quality Assurance Manager — error interception and system stability.

    Monitors all error reports, detects recurring patterns,
    auto-diagnoses common failures, and escalates unresolvable issues.
    """

    def __init__(
        self,
        chain: TradeChain,
        error_threshold: int = 3,
        auto_pause_threshold: int = 5,
    ) -> None:
        super().__init__(
            agent_id="qa-manager",
            role="qa-manager",
            chain=chain,
            loop_interval=5.0,
        )
        self.subscribe_to("error", "trade", "risk")

        self._error_log: list[ErrorRecord] = []
        self._bot_error_counts: dict[str, int] = defaultdict(int)
        self._error_patterns: dict[str, int] = defaultdict(int)
        self._error_threshold = error_threshold
        self._auto_pause_threshold = auto_pause_threshold
        self._diagnosed_issues: list[dict] = []

    async def execute(self) -> None:
        if self.metrics["cycles"] % 20 == 0 and self._error_log:
            await self._scan_for_patterns()

    async def handle_message(self, message: Message) -> None:
        if message.type == MessageType.ERROR_REPORT:
            await self._process_error(message)
        elif message.type == MessageType.TRADE_EXECUTED:
            self._validate_trade(message)
        elif message.type == MessageType.RISK_ALERT:
            await self._log_risk_event(message)

    async def _process_error(self, message: Message) -> None:
        p = message.payload
        agent_id = p.get("agent_id", message.sender_id)
        error_detail = p.get("error", "unknown")

        error_type = self._classify_error(error_detail)
        record = ErrorRecord(
            agent_id=agent_id,
            error_type=error_type,
            details=error_detail,
            timestamp=datetime.now(timezone.utc),
        )
        self._error_log.append(record)
        self._bot_error_counts[agent_id] += 1
        self._error_patterns[error_type] += 1

        diagnosis = self._diagnose(error_type, error_detail)
        if diagnosis:
            record.resolved = True
            self._diagnosed_issues.append({
                "agent_id": agent_id,
                "error_type": error_type,
                "diagnosis": diagnosis,
                "auto_resolved": True,
                "timestamp": record.timestamp.isoformat(),
            })
            await self.send(
                MessageType.AGENT_CHAT,
                {
                    "from": "qa-manager",
                    "to": agent_id,
                    "diagnosis": diagnosis,
                    "action": "auto_fix_applied",
                },
                target_id=agent_id,
            )
            logger.info(f"QA auto-diagnosed {error_type} for {agent_id}: {diagnosis}")

        if self._bot_error_counts[agent_id] >= self._auto_pause_threshold:
            await self._request_bot_pause(agent_id)

    def _classify_error(self, error_detail: str) -> str:
        detail_lower = error_detail.lower()
        if "timeout" in detail_lower or "timed out" in detail_lower:
            return "api_timeout"
        if "rate limit" in detail_lower or "429" in detail_lower:
            return "rate_limit"
        if "insufficient" in detail_lower or "balance" in detail_lower:
            return "insufficient_funds"
        if "connection" in detail_lower or "network" in detail_lower:
            return "network_error"
        if "invalid" in detail_lower or "malformed" in detail_lower:
            return "invalid_request"
        if "auth" in detail_lower or "401" in detail_lower or "403" in detail_lower:
            return "auth_error"
        return "unknown"

    def _diagnose(self, error_type: str, detail: str) -> str | None:
        diagnoses = {
            "api_timeout": "Exchange API timeout — likely transient. Bot should retry with exponential backoff.",
            "rate_limit": "Rate limit hit — Ops Manager should reduce this bot's polling frequency.",
            "insufficient_funds": "Insufficient balance for order — bot should check balance before placing trades.",
            "network_error": "Network connectivity issue — transient, retry in 30s.",
            "auth_error": "Authentication failed — API keys may be expired or invalid. User should re-enter keys.",
            "invalid_request": "Malformed request sent to exchange — possible bug in trade parameter construction.",
        }
        return diagnoses.get(error_type)

    def _validate_trade(self, message: Message) -> None:
        p = message.payload
        quantity = float(p.get("quantity", 0))
        price = float(p.get("filled_price", p.get("price", 0)))

        if quantity <= 0:
            self._flag_anomaly(message.sender_id, "zero_or_negative_quantity", p)
        if price <= 0:
            self._flag_anomaly(message.sender_id, "zero_or_negative_price", p)
        if quantity * price > 50000:
            self._flag_anomaly(message.sender_id, "oversized_trade", p)

    def _flag_anomaly(self, agent_id: str, anomaly_type: str, trade_data: dict) -> None:
        self._diagnosed_issues.append({
            "agent_id": agent_id,
            "error_type": f"trade_anomaly:{anomaly_type}",
            "trade_data": trade_data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        logger.warning(f"Trade anomaly [{anomaly_type}] from {agent_id}: {trade_data}")

    async def _request_bot_pause(self, agent_id: str) -> None:
        await self.send(
            MessageType.SYSTEM_COMMAND,
            {
                "command": "pause_bot",
                "agent_id": agent_id,
                "reason": f"Exceeded error threshold ({self._auto_pause_threshold} errors)",
            },
            target_id="ops-manager",
            priority=Priority.HIGH,
        )
        logger.warning(f"QA requested pause for {agent_id} — too many errors")

    async def _scan_for_patterns(self) -> None:
        for error_type, count in self._error_patterns.items():
            if count >= self._error_threshold:
                await self.send(
                    MessageType.AGENT_CHAT,
                    {
                        "from": "qa-manager",
                        "alert": "recurring_pattern",
                        "error_type": error_type,
                        "occurrences": count,
                        "recommendation": f"Systemic {error_type} detected ({count} occurrences). Investigate root cause.",
                    },
                )

    def get_qa_summary(self) -> dict:
        unresolved = [e for e in self._error_log if not e.resolved]
        return {
            "total_errors": len(self._error_log),
            "unresolved": len(unresolved),
            "resolved": len(self._error_log) - len(unresolved),
            "error_patterns": dict(self._error_patterns),
            "bot_error_counts": dict(self._bot_error_counts),
            "recent_diagnoses": self._diagnosed_issues[-10:],
        }
