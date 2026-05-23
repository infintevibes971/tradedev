import random
from decimal import Decimal

from app.agents.traders.base_trader import Signal, TradingBot
from app.chain.tradechain import TradeChain
from app.exchange.adapter import ExchangeAdapter


class SentimentBot(TradingBot):
    """Trades based on market sentiment signals.

    In production, this would integrate with an LLM to analyze news/social media.
    Currently uses a simulated sentiment score for demonstration.
    """

    def __init__(
        self,
        agent_id: str,
        chain: TradeChain,
        exchange: ExchangeAdapter,
        symbol: str = "BTC/USDT",
        buy_threshold: float = 0.6,
        sell_threshold: float = -0.6,
        **kwargs,
    ) -> None:
        super().__init__(
            agent_id=agent_id,
            strategy_name="sentiment",
            chain=chain,
            exchange=exchange,
            symbol=symbol,
            **kwargs,
        )
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold
        self._sentiment_score: float = 0.0
        self._sentiment_source: str = "simulated"

    async def generate_signal(self) -> Signal:
        self._sentiment_score = await self._fetch_sentiment()

        if self._sentiment_score >= self.buy_threshold:
            return Signal.BUY
        elif self._sentiment_score <= self.sell_threshold:
            return Signal.SELL

        return Signal.HOLD

    async def _fetch_sentiment(self) -> float:
        """Simulated sentiment score between -1.0 and 1.0.

        TODO: Replace with LLM-powered sentiment analysis of
        news feeds, Twitter/X, and on-chain metrics.
        """
        self._sentiment_score = random.gauss(0, 0.4)
        return max(-1.0, min(1.0, self._sentiment_score))

    def get_status(self) -> dict:
        base = super().get_status()
        base["sentiment_score"] = round(self._sentiment_score, 3)
        base["sentiment_source"] = self._sentiment_source
        return base
