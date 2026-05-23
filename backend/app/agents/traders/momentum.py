from collections import deque
from decimal import Decimal

from app.agents.traders.base_trader import Signal, TradingBot
from app.chain.tradechain import TradeChain
from app.exchange.adapter import ExchangeAdapter


class MomentumBot(TradingBot):
    """Follows the trend — buys on sustained upward momentum, sells on downward.

    Uses rate-of-change over a lookback window. Profitable in trending markets.
    """

    def __init__(
        self,
        agent_id: str,
        chain: TradeChain,
        exchange: ExchangeAdapter,
        symbol: str = "BTC/USDT",
        lookback: int = 14,
        momentum_threshold: float = 0.03,
        **kwargs,
    ) -> None:
        super().__init__(
            agent_id=agent_id,
            strategy_name="momentum",
            chain=chain,
            exchange=exchange,
            symbol=symbol,
            **kwargs,
        )
        self.lookback = lookback
        self.momentum_threshold = Decimal(str(momentum_threshold))
        self._prices: deque[Decimal] = deque(maxlen=lookback + 1)

    async def generate_signal(self) -> Signal:
        ticker = await self.exchange.get_ticker(self.symbol)
        price = ticker["last"]
        self._prices.append(price)

        if len(self._prices) <= self.lookback:
            return Signal.HOLD

        old_price = self._prices[0]
        if old_price == 0:
            return Signal.HOLD

        roc = (price - old_price) / old_price

        if roc > self.momentum_threshold:
            return Signal.BUY
        elif roc < -self.momentum_threshold:
            return Signal.SELL

        return Signal.HOLD
