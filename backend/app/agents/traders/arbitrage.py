from decimal import Decimal

from app.agents.traders.base_trader import Signal, TradingBot
from app.chain.tradechain import TradeChain
from app.exchange.adapter import ExchangeAdapter


class ArbitrageBot(TradingBot):
    """Detects price discrepancies between a symbol pair and its components.

    Monitors the spread between two correlated assets. When the spread
    deviates beyond a threshold, it signals a trade expecting mean reversion
    of the spread (statistical arbitrage / pairs trading).
    """

    def __init__(
        self,
        agent_id: str,
        chain: TradeChain,
        exchange: ExchangeAdapter,
        symbol: str = "ETH/USDT",
        pair_symbol: str = "BTC/USDT",
        spread_threshold: float = 0.015,
        **kwargs,
    ) -> None:
        super().__init__(
            agent_id=agent_id,
            strategy_name="arbitrage",
            chain=chain,
            exchange=exchange,
            symbol=symbol,
            **kwargs,
        )
        self.pair_symbol = pair_symbol
        self.spread_threshold = Decimal(str(spread_threshold))
        self._historical_ratio: list[Decimal] = []
        self._ratio_window = 30

    async def generate_signal(self) -> Signal:
        ticker_a = await self.exchange.get_ticker(self.symbol)
        ticker_b = await self.exchange.get_ticker(self.pair_symbol)

        price_a = ticker_a["last"]
        price_b = ticker_b["last"]

        if price_b == 0:
            return Signal.HOLD

        current_ratio = price_a / price_b
        self._historical_ratio.append(current_ratio)

        if len(self._historical_ratio) > self._ratio_window:
            self._historical_ratio = self._historical_ratio[-self._ratio_window:]

        if len(self._historical_ratio) < self._ratio_window:
            return Signal.HOLD

        mean_ratio = sum(self._historical_ratio) / len(self._historical_ratio)
        if mean_ratio == 0:
            return Signal.HOLD

        deviation = (current_ratio - mean_ratio) / mean_ratio

        if deviation < -self.spread_threshold:
            return Signal.BUY
        elif deviation > self.spread_threshold:
            return Signal.SELL

        return Signal.HOLD

    def get_status(self) -> dict:
        base = super().get_status()
        base["pair_symbol"] = self.pair_symbol
        base["ratio_samples"] = len(self._historical_ratio)
        return base
