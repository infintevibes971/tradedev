import logging
from decimal import Decimal
from typing import Any

from app.agents.registry import AgentRegistry
from app.agents.traders.arbitrage import ArbitrageBot
from app.agents.traders.base_trader import TradingBot
from app.agents.traders.grid import GridBot
from app.agents.traders.mean_reversion import MeanReversionBot
from app.agents.traders.momentum import MomentumBot
from app.agents.traders.sentiment import SentimentBot
from app.chain.tradechain import TradeChain
from app.exchange.adapter import ExchangeAdapter

logger = logging.getLogger(__name__)

STRATEGY_MAP: dict[str, type[TradingBot]] = {
    "mean_reversion": MeanReversionBot,
    "momentum": MomentumBot,
    "grid": GridBot,
    "sentiment": SentimentBot,
    "arbitrage": ArbitrageBot,
}


class AgentFactory:
    """Spawns, configures, and registers trading bots dynamically.

    Supports creating individual bots, batch-spawning fleets,
    and listing available strategy templates.
    """

    def __init__(
        self,
        chain: TradeChain,
        registry: AgentRegistry,
        exchange: ExchangeAdapter,
    ) -> None:
        self.chain = chain
        self.registry = registry
        self.exchange = exchange
        self._spawn_counter: dict[str, int] = {}

    def _next_id(self, strategy: str) -> str:
        count = self._spawn_counter.get(strategy, 0) + 1
        self._spawn_counter[strategy] = count
        return f"{strategy}-{count:03d}"

    async def create_bot(
        self,
        strategy: str,
        symbol: str = "BTC/USDT",
        agent_id: str | None = None,
        trade_size: Decimal = Decimal("0.01"),
        autostart: bool = True,
        **strategy_params: Any,
    ) -> TradingBot:
        if strategy not in STRATEGY_MAP:
            raise ValueError(
                f"Unknown strategy '{strategy}'. Available: {list(STRATEGY_MAP.keys())}"
            )

        bot_id = agent_id or self._next_id(strategy)
        bot_class = STRATEGY_MAP[strategy]

        bot = bot_class(
            agent_id=bot_id,
            chain=self.chain,
            exchange=self.exchange,
            symbol=symbol,
            trade_size=trade_size,
            **strategy_params,
        )

        await self.registry.register(bot, autostart=autostart)
        logger.info(f"Factory spawned {strategy} bot: {bot_id} on {symbol}")
        return bot

    async def create_fleet(
        self,
        strategy: str,
        count: int,
        symbols: list[str] | None = None,
        **strategy_params: Any,
    ) -> list[TradingBot]:
        if symbols is None:
            symbols = ["BTC/USDT"]

        bots = []
        for i in range(count):
            symbol = symbols[i % len(symbols)]
            bot = await self.create_bot(
                strategy=strategy,
                symbol=symbol,
                **strategy_params,
            )
            bots.append(bot)

        logger.info(f"Factory spawned fleet: {count}x {strategy}")
        return bots

    async def create_mixed_fleet(
        self,
        config: list[dict[str, Any]],
    ) -> list[TradingBot]:
        """Spawn a diverse fleet from a config list.

        Example config:
            [
                {"strategy": "mean_reversion", "count": 10, "symbols": ["BTC/USDT", "ETH/USDT"]},
                {"strategy": "momentum", "count": 10, "symbols": ["SOL/USDT"]},
                {"strategy": "grid", "count": 10, "symbols": ["BTC/USDT"]},
            ]
        """
        all_bots = []
        for entry in config:
            strategy = entry.pop("strategy")
            count = entry.pop("count", 1)
            symbols = entry.pop("symbols", None)
            bots = await self.create_fleet(
                strategy=strategy,
                count=count,
                symbols=symbols,
                **entry,
            )
            all_bots.extend(bots)

        logger.info(f"Mixed fleet spawned: {len(all_bots)} total bots")
        return all_bots

    @staticmethod
    def list_strategies() -> list[dict[str, str]]:
        descriptions = {
            "mean_reversion": "Buys below moving average, sells above. Best in ranging markets.",
            "momentum": "Follows trends via rate-of-change. Best in trending markets.",
            "grid": "Places orders at fixed intervals. Profits from oscillation.",
            "sentiment": "Trades on sentiment signals. Integrates with LLM analysis.",
            "arbitrage": "Exploits price ratio deviations between correlated pairs.",
        }
        return [
            {"name": name, "description": descriptions.get(name, "")}
            for name in STRATEGY_MAP
        ]

    @property
    def total_spawned(self) -> int:
        return sum(self._spawn_counter.values())
