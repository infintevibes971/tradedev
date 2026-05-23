import logging
from decimal import Decimal
from enum import Enum

from app.agents.base import BaseAgent
from app.chain.messages import Message, MessageType, Priority
from app.chain.tradechain import TradeChain
from app.exchange.adapter import ExchangeAdapter

logger = logging.getLogger(__name__)


class Signal(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class TradingBot(BaseAgent):
    """Base class for all trading strategy bots.

    Subclasses implement generate_signal() — the strategy logic.
    Everything else (capital management, order execution, reporting)
    is handled here.
    """

    def __init__(
        self,
        agent_id: str,
        strategy_name: str,
        chain: TradeChain,
        exchange: ExchangeAdapter,
        symbol: str = "BTC/USDT",
        trade_size: Decimal = Decimal("0.01"),
        loop_interval: float = 10.0,
    ) -> None:
        super().__init__(
            agent_id=agent_id,
            role=f"trader:{strategy_name}",
            chain=chain,
            loop_interval=loop_interval,
        )
        self.subscribe_to("system", "capital")

        self.strategy_name = strategy_name
        self.exchange = exchange
        self.symbol = symbol
        self.trade_size = trade_size

        self.position: Decimal = Decimal("0")
        self.entry_price: Decimal = Decimal("0")
        self.allocated_capital: Decimal = Decimal("0")
        self.realized_pnl: Decimal = Decimal("0")
        self.trade_history: list[dict] = []

    async def generate_signal(self) -> Signal:
        """Override in subclass. Analyze market data and return a trading signal."""
        return Signal.HOLD

    async def execute(self) -> None:
        try:
            signal = await self.generate_signal()
        except Exception:
            self.metrics["errors"] += 1
            self.logger.exception("Signal generation failed")
            await self.send(
                MessageType.ERROR_REPORT,
                {"agent_id": self.agent_id, "error": "Signal generation failure"},
            )
            return

        if signal == Signal.HOLD:
            return

        await self._execute_signal(signal)

    async def _execute_signal(self, signal: Signal) -> None:
        ticker = await self.exchange.get_ticker(self.symbol)
        current_price = ticker["last"]

        if signal == Signal.BUY and self.position <= 0:
            order = await self.exchange.place_order(
                self.symbol, "buy", self.trade_size
            )
            if order["status"] == "filled":
                fill_price = Decimal(str(order["filled_price"]))
                pnl = Decimal("0")
                if self.position < 0:
                    pnl = (self.entry_price - fill_price) * abs(self.position)
                    self.realized_pnl += pnl
                self.position = self.trade_size
                self.entry_price = fill_price
                await self._report_trade(order, pnl)
            else:
                self.logger.warning(f"Order rejected: {order.get('reason')}")

        elif signal == Signal.SELL and self.position > 0:
            order = await self.exchange.place_order(
                self.symbol, "sell", self.position
            )
            if order["status"] == "filled":
                fill_price = Decimal(str(order["filled_price"]))
                pnl = (fill_price - self.entry_price) * self.position
                self.realized_pnl += pnl
                await self._report_trade(order, pnl)
                self.position = Decimal("0")
                self.entry_price = Decimal("0")

    async def _report_trade(self, order: dict, pnl: Decimal) -> None:
        trade_data = {
            "agent_id": self.agent_id,
            "strategy": self.strategy_name,
            "symbol": self.symbol,
            "side": order["side"],
            "quantity": order["quantity"],
            "filled_price": order["filled_price"],
            "pnl": str(pnl),
        }
        self.trade_history.append(trade_data)
        await self.send(MessageType.TRADE_EXECUTED, trade_data)

    async def handle_message(self, message: Message) -> None:
        if message.type == MessageType.CAPITAL_RESPONSE and message.target_id == self.agent_id:
            self._handle_capital_response(message)
        elif message.type == MessageType.SYSTEM_COMMAND:
            self._handle_system_command(message)

    def _handle_capital_response(self, message: Message) -> None:
        if message.payload.get("approved"):
            amount = Decimal(str(message.payload["amount"]))
            self.allocated_capital += amount
            self.logger.info(f"Capital received: {amount}")

    def _handle_system_command(self, message: Message) -> None:
        cmd = message.payload.get("command")
        target = message.payload.get("agent_id")
        if target != self.agent_id:
            return
        if cmd == "reduce_position":
            new_alloc = Decimal(str(message.payload.get("new_allocation", "0")))
            self.allocated_capital = new_alloc
            self.logger.warning(f"Capital reduced to {new_alloc}")
        elif cmd == "pause_bot":
            self.pause()
            self.logger.warning("Paused by system command")

    async def request_capital(self, amount: Decimal) -> None:
        await self.send(
            MessageType.CAPITAL_REQUEST,
            {"amount": str(amount), "strategy": self.strategy_name},
            target_id="ops-manager",
        )

    def get_status(self) -> dict:
        base = super().get_status()
        base.update({
            "strategy": self.strategy_name,
            "symbol": self.symbol,
            "position": str(self.position),
            "entry_price": str(self.entry_price),
            "realized_pnl": str(self.realized_pnl),
            "total_trades": len(self.trade_history),
        })
        return base
