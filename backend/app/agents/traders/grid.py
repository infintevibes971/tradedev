from decimal import Decimal

from app.agents.traders.base_trader import Signal, TradingBot
from app.chain.tradechain import TradeChain
from app.exchange.adapter import ExchangeAdapter


class GridBot(TradingBot):
    """Places buy/sell orders at fixed price intervals around a center price.

    Inspired by Pionex grid bots. Profits from price oscillation within a range.
    """

    def __init__(
        self,
        agent_id: str,
        chain: TradeChain,
        exchange: ExchangeAdapter,
        symbol: str = "BTC/USDT",
        grid_levels: int = 10,
        grid_spread: float = 0.01,
        **kwargs,
    ) -> None:
        super().__init__(
            agent_id=agent_id,
            strategy_name="grid",
            chain=chain,
            exchange=exchange,
            symbol=symbol,
            **kwargs,
        )
        self.grid_levels = grid_levels
        self.grid_spread = Decimal(str(grid_spread))
        self._center_price: Decimal | None = None
        self._grid_lines: list[Decimal] = []
        self._last_grid_index: int | None = None

    async def generate_signal(self) -> Signal:
        ticker = await self.exchange.get_ticker(self.symbol)
        price = ticker["last"]

        if self._center_price is None:
            self._center_price = price
            self._build_grid(price)
            return Signal.HOLD

        current_index = self._find_grid_index(price)
        if self._last_grid_index is None:
            self._last_grid_index = current_index
            return Signal.HOLD

        if current_index < self._last_grid_index:
            self._last_grid_index = current_index
            return Signal.BUY
        elif current_index > self._last_grid_index:
            self._last_grid_index = current_index
            return Signal.SELL

        return Signal.HOLD

    def _build_grid(self, center: Decimal) -> None:
        self._grid_lines = []
        half = self.grid_levels // 2
        for i in range(-half, half + 1):
            level = center * (1 + self.grid_spread * i)
            self._grid_lines.append(level)
        self._grid_lines.sort()

    def _find_grid_index(self, price: Decimal) -> int:
        for i, level in enumerate(self._grid_lines):
            if price < level:
                return i
        return len(self._grid_lines)
