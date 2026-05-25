"""Sentiment bot — LLM-powered trading strategy.

This bot asks the configured AI providers (Claude, Gemini, ChatGPT) for
a BUY/SELL/HOLD opinion based on the current market data. It's the
primary consumer of the multi-LLM registry.

Falls back to simulated sentiment if no AI providers are configured.
"""

import random
from decimal import Decimal

from app.agents.traders.base_trader import Signal, TradingBot
from app.ai.registry import is_available as ai_available
from app.chain.tradechain import TradeChain
from app.exchange.adapter import ExchangeAdapter


class SentimentBot(TradingBot):
    """Trades based on AI-powered market sentiment analysis.

    Uses the multi-LLM registry to consult Claude, Gemini, or ChatGPT.
    The AI returns BUY/SELL/HOLD with a confidence score (0-100).
    The bot only acts when confidence exceeds the threshold.

    Falls back to simulated sentiment if no AI providers are configured.
    """

    def __init__(
        self,
        agent_id: str,
        chain: TradeChain,
        exchange: ExchangeAdapter,
        symbol: str = "BTC/USDT",
        confidence_threshold: int = 60,
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
        self.confidence_threshold = confidence_threshold
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold
        self._sentiment_score: float = 0.0
        self._sentiment_source: str = "none"
        self._last_ai_action: str = "HOLD"
        self._last_ai_confidence: int = 0
        self._last_ai_reasoning: str = ""

    async def generate_signal(self) -> Signal:
        """Ask AI for an opinion, fall back to simulated sentiment."""

        if ai_available():
            return await self._generate_ai_signal()

        # Fallback: simulated sentiment (original behavior)
        self._sentiment_source = "simulated"
        self._sentiment_score = await self._fetch_simulated_sentiment()

        if self._sentiment_score >= self.buy_threshold:
            return Signal.BUY
        elif self._sentiment_score <= self.sell_threshold:
            return Signal.SELL

        return Signal.HOLD

    async def _generate_ai_signal(self) -> Signal:
        """Consult the AI registry for a trading opinion."""

        # Build lightweight indicator snapshot for context
        ticker = await self.exchange.get_ticker(self.symbol)
        indicators = {
            "price": float(ticker["last"]),
            "change_24h": float(ticker.get("change_24h", 0.0)),
            "volume_24h": float(ticker.get("volume_24h", 0.0)),
        }

        advice = await self.consult_ai(indicators=indicators)

        if advice is None or not advice.available:
            # AI call failed — fall back to simulated
            self._sentiment_source = "simulated (AI unavailable)"
            self._sentiment_score = await self._fetch_simulated_sentiment()
            if self._sentiment_score >= self.buy_threshold:
                return Signal.BUY
            elif self._sentiment_score <= self.sell_threshold:
                return Signal.SELL
            return Signal.HOLD

        # Store AI results for status reporting
        self._sentiment_source = advice.source
        self._last_ai_action = advice.action
        self._last_ai_confidence = advice.confidence
        self._last_ai_reasoning = advice.reasoning

        # Map AI confidence to our -1.0 to 1.0 sentiment scale
        if advice.action == "BUY":
            self._sentiment_score = advice.confidence / 100.0
        elif advice.action == "SELL":
            self._sentiment_score = -(advice.confidence / 100.0)
        else:
            self._sentiment_score = 0.0

        # Only act if AI is confident enough
        if advice.confidence < self.confidence_threshold:
            self.logger.info(
                "AI confidence %d%% below threshold %d%% — holding",
                advice.confidence, self.confidence_threshold,
            )
            return Signal.HOLD

        if advice.action == "BUY":
            return Signal.BUY
        elif advice.action == "SELL":
            return Signal.SELL

        return Signal.HOLD

    async def _fetch_simulated_sentiment(self) -> float:
        """Simulated sentiment score between -1.0 and 1.0.

        Used as fallback when no AI providers are configured.
        """
        score = random.gauss(0, 0.4)
        return max(-1.0, min(1.0, score))

    def get_status(self) -> dict:
        base = super().get_status()
        base["sentiment_score"] = round(self._sentiment_score, 3)
        base["sentiment_source"] = self._sentiment_source
        base["ai_powered"] = ai_available()
        base["last_ai_action"] = self._last_ai_action
        base["last_ai_confidence"] = self._last_ai_confidence
        base["confidence_threshold"] = self.confidence_threshold
        return base
