from collections import deque
from decimal import Decimal

from app.agents.traders.base_trader import Signal, TradingBot
from app.chain.tradechain import TradeChain
from app.exchange.adapter import ExchangeAdapter


class MeanReversionBot(TradingBot):
    """Buys when price drops below the moving average, sells when it rises above.

    Assumes prices oscillate around a mean — profitable in sideways/ranging markets.
    """

    def __init__(
        self,
        agent_id: str,
        chain: TradeChain,
        exchange: ExchangeAdapter,
        symbol: str = "BTC/USDT",
        window: int = 10,
        threshold: float = 0.008,
        **kwargs,
    ) -> None:
        super().__init__(
            agent_id=agent_id,
            strategy_name="mean_reversion",
            chain=chain,
            exchange=exchange,
            symbol=symbol,
            **kwargs,
        )
        self.window = window
        self.threshold = Decimal(str(threshold))
        self._prices: deque[Decimal] = deque(maxlen=window)

    async def generate_signal(self) -> Signal:
        ticker = await self.exchange.get_ticker(self.symbol)
        price = ticker["last"]
        self._prices.append(price)

        if len(self._prices) < self.window:
            return Signal.HOLD

        mean = sum(self._prices) / len(self._prices)
        deviation = (price - mean) / mean

        if deviation < -self.threshold:
            return Signal.BUY
        elif deviation > self.threshold:
            return Signal.SELL

        return Signal.HOLD
