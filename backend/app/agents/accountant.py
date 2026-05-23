import logging
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal

from app.agents.base import BaseAgent
from app.chain.messages import Message, MessageType, Priority
from app.chain.tradechain import TradeChain

logger = logging.getLogger(__name__)


class TradeRecord:
    __slots__ = ("agent_id", "symbol", "side", "quantity", "price", "pnl", "timestamp")

    def __init__(
        self,
        agent_id: str,
        symbol: str,
        side: str,
        quantity: Decimal,
        price: Decimal,
        pnl: Decimal,
        timestamp: datetime,
    ):
        self.agent_id = agent_id
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.price = price
        self.pnl = pnl
        self.timestamp = timestamp


class Accountant(BaseAgent):
    """Financial oversight agent.

    Tracks all executed trades, maintains per-bot P&L,
    calculates drawdowns and win rates, and generates periodic reports.
    """

    def __init__(self, chain: TradeChain, report_interval_cycles: int = 60) -> None:
        super().__init__(
            agent_id="accountant",
            role="accountant",
            chain=chain,
            loop_interval=5.0,
        )
        self.subscribe_to("trade", "capital")

        self._trades: list[TradeRecord] = []
        self._bot_pnl: dict[str, Decimal] = defaultdict(Decimal)
        self._bot_trade_count: dict[str, int] = defaultdict(int)
        self._bot_wins: dict[str, int] = defaultdict(int)
        self._total_pnl = Decimal("0")
        self._peak_balance = Decimal("0")
        self._report_interval = report_interval_cycles

    async def execute(self) -> None:
        if self.metrics["cycles"] > 0 and self.metrics["cycles"] % self._report_interval == 0:
            await self._publish_report()

    async def handle_message(self, message: Message) -> None:
        if message.type == MessageType.TRADE_EXECUTED:
            await self._record_trade(message)
        elif message.type == MessageType.CAPITAL_REQUEST:
            await self._assess_capital_request(message)

    async def _record_trade(self, message: Message) -> None:
        p = message.payload
        pnl = Decimal(str(p.get("pnl", "0")))
        record = TradeRecord(
            agent_id=p.get("agent_id", message.sender_id),
            symbol=p.get("symbol", ""),
            side=p.get("side", ""),
            quantity=Decimal(str(p.get("quantity", "0"))),
            price=Decimal(str(p.get("filled_price", p.get("price", "0")))),
            pnl=pnl,
            timestamp=datetime.now(timezone.utc),
        )
        self._trades.append(record)

        agent = record.agent_id
        self._bot_pnl[agent] += pnl
        self._bot_trade_count[agent] += 1
        if pnl > 0:
            self._bot_wins[agent] += 1
        self._total_pnl += pnl

        current_balance = self._total_pnl
        if current_balance > self._peak_balance:
            self._peak_balance = current_balance

        if pnl < Decimal("-500"):
            await self.send(
                MessageType.RISK_ALERT,
                {
                    "alert": "large_loss",
                    "agent_id": agent,
                    "pnl": str(pnl),
                    "symbol": record.symbol,
                },
                priority=Priority.HIGH,
            )
            logger.warning(f"RISK ALERT: {agent} lost {pnl} on {record.symbol}")

    async def _assess_capital_request(self, message: Message) -> None:
        requester = message.sender_id
        win_rate = self.get_win_rate(requester)
        bot_pnl = self._bot_pnl.get(requester, Decimal("0"))

        assessment = {
            "requester": requester,
            "win_rate": str(win_rate),
            "total_pnl": str(bot_pnl),
            "recommendation": "approve" if win_rate >= 0.4 or bot_pnl >= 0 else "deny",
            "reason": f"Win rate {win_rate:.1%}, cumulative P&L {bot_pnl}",
        }
        await self.send(
            MessageType.AGENT_CHAT,
            assessment,
            target_id="ops-manager",
        )

    async def _publish_report(self) -> None:
        report = self.generate_report()
        await self.send(MessageType.WEEKLY_REPORT, report)
        logger.info(f"Accountant published report: total P&L = {report['total_pnl']}")

    def get_win_rate(self, agent_id: str) -> float:
        total = self._bot_trade_count.get(agent_id, 0)
        if total == 0:
            return 0.0
        return self._bot_wins.get(agent_id, 0) / total

    def get_drawdown(self) -> Decimal:
        if self._peak_balance <= 0:
            return Decimal("0")
        return (self._peak_balance - self._total_pnl) / self._peak_balance

    def generate_report(self) -> dict:
        bot_summaries = {}
        for agent_id in self._bot_pnl:
            bot_summaries[agent_id] = {
                "pnl": str(self._bot_pnl[agent_id]),
                "trades": self._bot_trade_count[agent_id],
                "win_rate": f"{self.get_win_rate(agent_id):.1%}",
            }

        top_performers = sorted(
            self._bot_pnl.items(), key=lambda x: x[1], reverse=True
        )[:5]
        worst_performers = sorted(
            self._bot_pnl.items(), key=lambda x: x[1]
        )[:5]

        return {
            "total_pnl": str(self._total_pnl),
            "total_trades": len(self._trades),
            "active_bots": len(self._bot_pnl),
            "max_drawdown": str(self.get_drawdown()),
            "top_performers": [{"id": k, "pnl": str(v)} for k, v in top_performers],
            "worst_performers": [{"id": k, "pnl": str(v)} for k, v in worst_performers],
            "bot_summaries": bot_summaries,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
