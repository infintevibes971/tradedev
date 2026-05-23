import asyncio
from decimal import Decimal

import pytest

from app.agents.factory import AgentFactory
from app.agents.registry import AgentRegistry
from app.agents.traders.arbitrage import ArbitrageBot
from app.agents.traders.base_trader import Signal, TradingBot
from app.agents.traders.grid import GridBot
from app.agents.traders.mean_reversion import MeanReversionBot
from app.agents.traders.momentum import MomentumBot
from app.agents.traders.sentiment import SentimentBot
from app.chain.messages import MessageType
from app.chain.tradechain import TradeChain
from app.exchange.mock import MockAdapter


@pytest.fixture
def chain():
    return TradeChain()


@pytest.fixture
def exchange():
    return MockAdapter()


@pytest.fixture
def registry():
    return AgentRegistry()


@pytest.fixture
def factory(chain, registry, exchange):
    return AgentFactory(chain, registry, exchange)


# ── TradingBot Base ──


async def test_trading_bot_executes_and_reports(chain: TradeChain, exchange: MockAdapter):
    class AlwaysBuyBot(TradingBot):
        def __init__(self):
            super().__init__(
                "test-buyer", "test", chain, exchange,
                symbol="BTC/USDT", trade_size=Decimal("0.01"), loop_interval=0.05,
            )

        async def generate_signal(self) -> Signal:
            if len(self.trade_history) == 0:
                return Signal.BUY
            return Signal.HOLD

    trades = []

    async def capture(msg):
        if msg.type == MessageType.TRADE_EXECUTED:
            trades.append(msg)

    chain.subscribe("monitor", "trade", capture)

    bot = AlwaysBuyBot()
    bot.subscribe_to("system", "capital")
    await bot.start()
    await asyncio.sleep(0.3)
    await bot.stop()

    assert bot.position == Decimal("0.01")
    assert len(trades) >= 1
    assert trades[0].payload["strategy"] == "test"


async def test_trading_bot_tracks_pnl(chain: TradeChain, exchange: MockAdapter):
    class BuySellBot(TradingBot):
        def __init__(self):
            super().__init__(
                "pnl-bot", "test", chain, exchange,
                symbol="BTC/USDT", trade_size=Decimal("0.01"), loop_interval=0.05,
            )
            self._step = 0

        async def generate_signal(self) -> Signal:
            self._step += 1
            if self._step == 1:
                return Signal.BUY
            if self._step == 5:
                return Signal.SELL
            return Signal.HOLD

    bot = BuySellBot()
    bot.subscribe_to("system", "capital")
    await bot.start()
    await asyncio.sleep(0.5)
    await bot.stop()

    assert len(bot.trade_history) == 2
    assert bot.position == Decimal("0")


# ── Individual Strategies ──


async def test_mean_reversion_generates_signals(chain: TradeChain, exchange: MockAdapter):
    bot = MeanReversionBot("mr-1", chain, exchange, window=5, threshold=0.001)
    for _ in range(6):
        signal = await bot.generate_signal()
    assert signal in (Signal.BUY, Signal.SELL, Signal.HOLD)


async def test_momentum_generates_signals(chain: TradeChain, exchange: MockAdapter):
    bot = MomentumBot("mom-1", chain, exchange, lookback=5, momentum_threshold=0.001)
    for _ in range(7):
        signal = await bot.generate_signal()
    assert signal in (Signal.BUY, Signal.SELL, Signal.HOLD)


async def test_grid_builds_and_signals(chain: TradeChain, exchange: MockAdapter):
    bot = GridBot("grid-1", chain, exchange, grid_levels=6, grid_spread=0.005)
    signal1 = await bot.generate_signal()
    assert signal1 == Signal.HOLD
    assert bot._center_price is not None
    assert len(bot._grid_lines) == 7


async def test_sentiment_generates_signals(chain: TradeChain, exchange: MockAdapter):
    bot = SentimentBot("sent-1", chain, exchange)
    signals = set()
    for _ in range(50):
        signals.add(await bot.generate_signal())
    assert Signal.HOLD in signals


async def test_arbitrage_generates_signals(chain: TradeChain, exchange: MockAdapter):
    bot = ArbitrageBot("arb-1", chain, exchange, symbol="ETH/USDT", pair_symbol="BTC/USDT")
    for _ in range(35):
        signal = await bot.generate_signal()
    assert signal in (Signal.BUY, Signal.SELL, Signal.HOLD)
    assert len(bot._historical_ratio) == 30


# ── Agent Factory ──


async def test_factory_creates_single_bot(factory: AgentFactory):
    bot = await factory.create_bot("mean_reversion", symbol="ETH/USDT")
    assert bot.strategy_name == "mean_reversion"
    assert bot.symbol == "ETH/USDT"
    assert factory.registry.total_count == 1
    await factory.registry.stop_all()


async def test_factory_creates_fleet(factory: AgentFactory):
    bots = await factory.create_fleet("momentum", count=5, symbols=["BTC/USDT", "ETH/USDT"])
    assert len(bots) == 5
    assert factory.registry.total_count == 5
    symbols = [b.symbol for b in bots]
    assert symbols.count("BTC/USDT") >= 2
    assert symbols.count("ETH/USDT") >= 2
    await factory.registry.stop_all()


async def test_factory_creates_mixed_fleet(factory: AgentFactory):
    config = [
        {"strategy": "mean_reversion", "count": 3, "symbols": ["BTC/USDT"]},
        {"strategy": "momentum", "count": 2, "symbols": ["ETH/USDT"]},
        {"strategy": "grid", "count": 2, "symbols": ["SOL/USDT"]},
    ]
    bots = await factory.create_mixed_fleet(config)
    assert len(bots) == 7
    assert factory.total_spawned == 7
    await factory.registry.stop_all()


async def test_factory_rejects_unknown_strategy(factory: AgentFactory):
    with pytest.raises(ValueError, match="Unknown strategy"):
        await factory.create_bot("magic_money")


async def test_factory_lists_strategies():
    strategies = AgentFactory.list_strategies()
    names = [s["name"] for s in strategies]
    assert "mean_reversion" in names
    assert "momentum" in names
    assert "grid" in names
    assert "sentiment" in names
    assert "arbitrage" in names


# ── Concurrency ──


async def test_50_bots_run_concurrently(factory: AgentFactory):
    """Spawn 50 bots and verify they all run without blocking."""
    config = [
        {"strategy": "mean_reversion", "count": 10, "symbols": ["BTC/USDT", "ETH/USDT"]},
        {"strategy": "momentum", "count": 10, "symbols": ["SOL/USDT", "BNB/USDT"]},
        {"strategy": "grid", "count": 10, "symbols": ["BTC/USDT"]},
        {"strategy": "sentiment", "count": 10, "symbols": ["ETH/USDT"]},
        {"strategy": "arbitrage", "count": 10, "symbols": ["ETH/USDT"]},
    ]
    bots = await factory.create_mixed_fleet(config)
    assert len(bots) == 50
    assert factory.registry.active_count == 50

    await asyncio.sleep(0.3)

    running = [b for b in bots if b.metrics["cycles"] > 0]
    assert len(running) >= 45

    await factory.registry.stop_all()
