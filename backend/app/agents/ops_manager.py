import logging
from collections import defaultdict
from decimal import Decimal

from app.agents.base import AgentStatus, BaseAgent
from app.chain.messages import Message, MessageType, Priority
from app.chain.tradechain import TradeChain

logger = logging.getLogger(__name__)


class OpsManager(BaseAgent):
    """Operations Manager — resource allocator and system administrator.

    Manages capital distribution among trading bots, monitors API rate limits,
    handles capital requests, and provides operational status reports.
    """

    def __init__(
        self,
        chain: TradeChain,
        total_capital: Decimal = Decimal("100000"),
        max_allocation_pct: Decimal = Decimal("0.10"),
    ) -> None:
        super().__init__(
            agent_id="ops-manager",
            role="ops-manager",
            chain=chain,
            loop_interval=10.0,
        )
        self.subscribe_to("capital", "status", "risk", "agent")

        self.total_capital = total_capital
        self.max_allocation_pct = max_allocation_pct
        self._allocations: dict[str, Decimal] = {}
        self._rate_limit_usage: dict[str, int] = defaultdict(int)
        self._rate_limit_max: int = 1200
        self._pending_requests: list[dict] = []
        self._paused_bots: set[str] = set()

    @property
    def allocated_capital(self) -> Decimal:
        return sum(self._allocations.values(), Decimal("0"))

    @property
    def available_capital(self) -> Decimal:
        return self.total_capital - self.allocated_capital

    async def execute(self) -> None:
        if self.metrics["cycles"] % 30 == 0:
            await self._broadcast_status()

    async def handle_message(self, message: Message) -> None:
        if message.type == MessageType.CAPITAL_REQUEST:
            await self._handle_capital_request(message)
        elif message.type == MessageType.RISK_ALERT:
            await self._handle_risk_alert(message)
        elif message.type == MessageType.STATUS_REPORT:
            self._update_rate_limits(message)
        elif message.type == MessageType.AGENT_CHAT:
            if message.payload.get("recommendation"):
                await self._process_accountant_assessment(message)

    async def _handle_capital_request(self, message: Message) -> None:
        requester = message.sender_id
        requested_amount = Decimal(str(message.payload.get("amount", "0")))
        max_allowed = self.total_capital * self.max_allocation_pct

        if requester in self._paused_bots:
            await self.send(
                MessageType.CAPITAL_RESPONSE,
                {
                    "approved": False,
                    "reason": "Bot is paused due to risk alert",
                    "amount": "0",
                },
                target_id=requester,
            )
            return

        if requested_amount > max_allowed:
            requested_amount = max_allowed

        if requested_amount > self.available_capital:
            await self.send(
                MessageType.CAPITAL_RESPONSE,
                {
                    "approved": False,
                    "reason": f"Insufficient capital. Available: {self.available_capital}",
                    "amount": "0",
                },
                target_id=requester,
            )
            return

        self._pending_requests.append({
            "requester": requester,
            "amount": requested_amount,
            "payload": message.payload,
        })

        await self.send(
            MessageType.CAPITAL_REQUEST,
            {"requester": requester, "amount": str(requested_amount)},
            target_id="accountant",
        )

    async def _process_accountant_assessment(self, message: Message) -> None:
        recommendation = message.payload.get("recommendation")
        requester = message.payload.get("requester")

        pending = None
        for req in self._pending_requests:
            if req["requester"] == requester:
                pending = req
                break

        if not pending:
            return
        self._pending_requests.remove(pending)

        if recommendation == "approve":
            amount = pending["amount"]
            self._allocations[requester] = (
                self._allocations.get(requester, Decimal("0")) + amount
            )
            await self.send(
                MessageType.CAPITAL_RESPONSE,
                {"approved": True, "amount": str(amount)},
                target_id=requester,
            )
            logger.info(f"Capital approved: {amount} for {requester}")
        else:
            await self.send(
                MessageType.CAPITAL_RESPONSE,
                {
                    "approved": False,
                    "reason": message.payload.get("reason", "Denied by accountant review"),
                    "amount": "0",
                },
                target_id=requester,
            )
            logger.info(f"Capital denied for {requester}: {message.payload.get('reason')}")

    async def _handle_risk_alert(self, message: Message) -> None:
        agent_id = message.payload.get("agent_id", "")
        alert_type = message.payload.get("alert", "")

        if alert_type == "large_loss":
            self._paused_bots.add(agent_id)
            current_alloc = self._allocations.get(agent_id, Decimal("0"))
            reduced = (current_alloc * Decimal("0.5")).quantize(Decimal("0.01"))
            self._allocations[agent_id] = reduced

            await self.send(
                MessageType.SYSTEM_COMMAND,
                {
                    "command": "reduce_position",
                    "agent_id": agent_id,
                    "new_allocation": str(reduced),
                    "reason": "Risk alert — capital halved",
                },
                target_id=agent_id,
            )
            logger.warning(f"Risk response: halved {agent_id}'s capital to {reduced}")

    def _update_rate_limits(self, message: Message) -> None:
        agent_id = message.sender_id
        api_calls = message.payload.get("api_calls", 0)
        self._rate_limit_usage[agent_id] = api_calls

    def get_allocation(self, agent_id: str) -> Decimal:
        return self._allocations.get(agent_id, Decimal("0"))

    def reinstate_bot(self, agent_id: str) -> None:
        self._paused_bots.discard(agent_id)

    async def _broadcast_status(self) -> None:
        total_rate = sum(self._rate_limit_usage.values())
        await self.send(
            MessageType.STATUS_REPORT,
            {
                "total_capital": str(self.total_capital),
                "allocated": str(self.allocated_capital),
                "available": str(self.available_capital),
                "active_allocations": len(self._allocations),
                "paused_bots": list(self._paused_bots),
                "rate_limit_usage": f"{total_rate}/{self._rate_limit_max}",
            },
        )

    def get_ops_summary(self) -> dict:
        return {
            "total_capital": str(self.total_capital),
            "allocated": str(self.allocated_capital),
            "available": str(self.available_capital),
            "allocations": {k: str(v) for k, v in self._allocations.items()},
            "paused_bots": list(self._paused_bots),
            "pending_requests": len(self._pending_requests),
        }
