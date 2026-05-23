"""Phase 7: Adversarial Testing

Simulates real-world failure modes:
1. Exchange API goes down (timeouts, connection refused)
2. Rogue bot sends invalid trades
3. Error cascade from rate limiting
4. QA Manager correctly intercepts and escalates
5. Ops Manager circuit-breaker behavior
6. System recovery after failures
"""

import asyncio
from decimal import Decimal
from typing import Any

import pytest

from app.agents.accountant import Accountant
from app.agents.base import AgentStatus, BaseAgent
from app.agents.factory import AgentFactory
from app.agents.ops_manager import OpsManager
from app.agents.qa_manager import QAManager
from app.agents.registry import AgentRegistry
from app.agents.traders.base_trader import Signal, TradingBot
from app.chain.messages import Message, MessageType, Priority
from app.chain.tradechain import TradeChain
from app.exchange.adapter import ExchangeAdapter
from app.exchange.mock import MockAdapter


# ── Faulty Exchange Adapters ──


class TimeoutExchange(ExchangeAdapter):
    """Simulates an exchange that times out on every call."""

    def __init__(self):
        super().__init__("timeout-exchange")
        self.call_count = 0

    async def get_ticker(self, symbol: str) -> dict[str, Any]:
        self.call_count += 1
        raise TimeoutError("Exchange API timeout after 30s")

    async def place_order(self, symbol, side, quantity, price=None):
        raise TimeoutError("Exchange API timeout")

    async def cancel_order(self, order_id, symbol):
        raise TimeoutError("Exchange API timeout")

    async def get_balance(self):
        raise TimeoutError("Exchange API timeout")

    async def get_order_book(self, symbol, depth=10):
        raise TimeoutError("Exchange API timeout")

    async def get_ohlcv(self, symbol, timeframe="1h", limit=100):
        raise TimeoutError("Exchange API timeout")


class IntermittentExchange(MockAdapter):
    """Exchange that fails every N calls, then recovers."""

    def __init__(self, fail_every: int = 3):
        super().__init__()
        self._call_count = 0
        self._fail_every = fail_every

    async def get_ticker(self, symbol: str) -> dict[str, Any]:
        self._call_count += 1
        if self._call_count % self._fail_every == 0:
            raise ConnectionError("Exchange connection reset")
        return await super().get_ticker(symbol)


class RateLimitedExchange(MockAdapter):
    """Exchange that returns 429 after N calls per window."""

    def __init__(self, max_calls: int = 5):
        super().__init__()
        self._call_count = 0
        self._max_calls = max_calls

    async def get_ticker(self, symbol: str) -> dict[str, Any]:
        self._call_count += 1
        if self._call_count > self._max_calls:
            raise Exception("429 Too Many Requests - Rate limit exceeded")
        return await super().get_ticker(symbol)


# ── Rogue Bots ──


class RogueBot(TradingBot):
    """Bot that always tries to buy enormous quantities."""

    def __init__(self, agent_id: str, chain: TradeChain, exchange: ExchangeAdapter):
        super().__init__(
            agent_id, "rogue", chain, exchange,
            symbol="BTC/USDT", trade_size=Decimal("99999"), loop_interval=0.05,
        )

    async def generate_signal(self) -> Signal:
        return Signal.BUY


class CrashBot(TradingBot):
    """Bot that crashes on every execution."""

    def __init__(self, agent_id: str, chain: TradeChain, exchange: ExchangeAdapter):
        super().__init__(
            agent_id, "crasher", chain, exchange,
            symbol="BTC/USDT", loop_interval=0.05,
        )

    async def generate_signal(self) -> Signal:
        raise RuntimeError("Segfault in strategy logic")


class SpamBot(TradingBot):
    """Bot that floods the TradeChain with messages."""

    def __init__(self, agent_id: str, chain: TradeChain, exchange: ExchangeAdapter):
        super().__init__(
            agent_id, "spammer", chain, exchange,
            symbol="BTC/USDT", loop_interval=0.01,
        )
        self.spam_count = 0

    async def generate_signal(self) -> Signal:
        self.spam_count += 1
        for _ in range(10):
            await self.send(
                MessageType.AGENT_CHAT,
                {"spam": True, "count": self.spam_count},
            )
        return Signal.HOLD


# ── Fixtures ──


@pytest.fixture
def chain():
    return TradeChain()


@pytest.fixture
def registry():
    return AgentRegistry()


# ── Test 1: Exchange Goes Down Completely ──


class TestExchangeDown:
    async def test_bot_survives_total_exchange_failure(self, chain: TradeChain):
        """Bot should not crash when exchange is completely unreachable."""
        exchange = TimeoutExchange()
        bot = TradingBot.__new__(TradingBot)
        # Use a simple subclass instead
        class TimeoutBot(TradingBot):
            async def generate_signal(self):
                ticker = await self.exchange.get_ticker(self.symbol)
                return Signal.BUY

        bot = TimeoutBot(
            "timeout-bot", "test", chain, exchange,
            symbol="BTC/USDT", loop_interval=0.05,
        )
        bot.subscribe_to("system")

        error_reports = []
        async def capture(msg):
            if msg.type == MessageType.ERROR_REPORT:
                error_reports.append(msg)
        chain.subscribe("monitor", "error", capture)

        await bot.start()
        await asyncio.sleep(0.5)
        await bot.stop()

        assert bot.metrics["errors"] > 0
        assert len(error_reports) > 0
        assert bot.status == AgentStatus.STOPPED
        assert exchange.call_count > 0

    async def test_fleet_survives_exchange_failure(self, chain: TradeChain, registry: AgentRegistry):
        """Other bots should keep running when one bot's exchange fails."""
        good_exchange = MockAdapter()
        bad_exchange = TimeoutExchange()

        class SimpleBot(TradingBot):
            async def generate_signal(self):
                await self.exchange.get_ticker(self.symbol)
                return Signal.HOLD

        good_bot = SimpleBot(
            "good-bot", "test", chain, good_exchange,
            symbol="BTC/USDT", loop_interval=0.05,
        )
        bad_bot = SimpleBot(
            "bad-bot", "test", chain, bad_exchange,
            symbol="BTC/USDT", loop_interval=0.05,
        )
        good_bot.subscribe_to("system")
        bad_bot.subscribe_to("system")

        await registry.register(good_bot)
        await registry.register(bad_bot)

        await asyncio.sleep(0.5)

        assert good_bot.metrics["cycles"] > 0
        assert good_bot.metrics["errors"] == 0
        assert bad_bot.metrics["errors"] > 0

        await registry.stop_all()


# ── Test 2: Intermittent Failures ──


class TestIntermittentFailures:
    async def test_bot_recovers_from_intermittent_errors(self, chain: TradeChain):
        """Bot should keep running through occasional failures."""
        exchange = IntermittentExchange(fail_every=3)

        class RecoveryBot(TradingBot):
            def __init__(self):
                super().__init__(
                    "recovery-bot", "test", chain, exchange,
                    symbol="BTC/USDT", loop_interval=0.05,
                )
                self.successful_ticks = 0

            async def generate_signal(self):
                await self.exchange.get_ticker(self.symbol)
                self.successful_ticks += 1
                return Signal.HOLD

        bot = RecoveryBot()
        bot.subscribe_to("system")
        await bot.start()
        await asyncio.sleep(1.0)
        await bot.stop()

        assert bot.successful_ticks > 0
        assert bot.metrics["errors"] > 0
        assert bot.metrics["cycles"] > bot.metrics["errors"]


# ── Test 3: Rogue Bot Behavior ──


class TestRogueBot:
    async def test_rogue_order_rejected_by_exchange(self, chain: TradeChain):
        """Oversized orders should be rejected at the exchange level."""
        exchange = MockAdapter()
        bot = RogueBot("rogue-1", chain, exchange)
        bot.subscribe_to("system", "capital")

        trades_executed = []
        async def capture(msg):
            if msg.type == MessageType.TRADE_EXECUTED:
                trades_executed.append(msg)
        chain.subscribe("monitor", "trade", capture)

        await bot.start()
        await asyncio.sleep(0.3)
        await bot.stop()

        # Rogue bot's 99999 BTC order should be rejected (insufficient balance)
        assert len(trades_executed) == 0

    async def test_qa_catches_rogue_trade_anomaly(self, chain: TradeChain):
        """QA Manager should flag trades with zero or negative quantities."""
        qa = QAManager(chain)
        await qa.start()

        # Simulate a trade with zero quantity sneaking through
        await chain.publish(Message(
            type=MessageType.TRADE_EXECUTED,
            sender_id="evil-bot",
            payload={
                "agent_id": "evil-bot",
                "symbol": "BTC/USDT",
                "side": "buy",
                "quantity": "0",
                "filled_price": "67000",
                "pnl": "0",
            },
        ))

        # Simulate oversized trade
        await chain.publish(Message(
            type=MessageType.TRADE_EXECUTED,
            sender_id="whale-bot",
            payload={
                "agent_id": "whale-bot",
                "symbol": "BTC/USDT",
                "side": "buy",
                "quantity": "1",
                "filled_price": "67000",
                "pnl": "0",
            },
        ))

        await asyncio.sleep(0.2)
        await qa.stop()

        anomalies = [
            d for d in qa._diagnosed_issues
            if "trade_anomaly" in d.get("error_type", "")
        ]
        assert len(anomalies) >= 1
        assert any("zero_or_negative_quantity" in a["error_type"] for a in anomalies)
        assert any("oversized_trade" in a["error_type"] for a in anomalies)


# ── Test 4: Crash Bot ──


class TestCrashBot:
    async def test_crash_bot_doesnt_take_down_system(self, chain: TradeChain, registry: AgentRegistry):
        """A bot that crashes every tick should not affect other agents."""
        exchange = MockAdapter()

        crash_bot = CrashBot("crash-1", chain, exchange)
        crash_bot.subscribe_to("system")

        class HealthyBot(TradingBot):
            def __init__(self):
                super().__init__(
                    "healthy-1", "steady", chain, exchange,
                    symbol="BTC/USDT", loop_interval=0.05,
                )
                self.ticks = 0

            async def generate_signal(self):
                self.ticks += 1
                return Signal.HOLD

        healthy = HealthyBot()
        healthy.subscribe_to("system")

        await registry.register(crash_bot)
        await registry.register(healthy)

        await asyncio.sleep(0.5)

        assert crash_bot.metrics["errors"] > 0
        assert healthy.ticks > 0
        assert healthy.metrics["errors"] == 0

        await registry.stop_all()


# ── Test 5: Error Cascade → QA Auto-Pause ──


class TestErrorCascade:
    async def test_qa_requests_pause_after_error_threshold(self, chain: TradeChain):
        """QA should request bot pause after 5 consecutive errors."""
        pause_commands = []

        async def capture(msg):
            if msg.type == MessageType.SYSTEM_COMMAND and msg.payload.get("command") == "pause_bot":
                pause_commands.append(msg)

        chain.subscribe_direct("ops-manager", capture)

        qa = QAManager(chain, auto_pause_threshold=3)
        await qa.start()

        for i in range(4):
            await chain.publish(Message(
                type=MessageType.ERROR_REPORT,
                sender_id="flaky-bot",
                payload={"agent_id": "flaky-bot", "error": f"Connection timeout #{i}"},
            ))
            await asyncio.sleep(0.05)

        await asyncio.sleep(0.2)
        await qa.stop()

        assert len(pause_commands) >= 1
        assert pause_commands[0].payload["agent_id"] == "flaky-bot"

    async def test_rate_limit_cascade(self, chain: TradeChain):
        """Multiple bots hitting rate limits should all be diagnosed."""
        qa = QAManager(chain)
        await qa.start()

        for bot_id in ["bot-1", "bot-2", "bot-3"]:
            await chain.publish(Message(
                type=MessageType.ERROR_REPORT,
                sender_id=bot_id,
                payload={"agent_id": bot_id, "error": "429 Too Many Requests"},
            ))
        await asyncio.sleep(0.2)
        await qa.stop()

        assert qa._error_patterns["rate_limit"] == 3
        assert all(d["auto_resolved"] for d in qa._diagnosed_issues)


# ── Test 6: Full Supervision Chain Under Stress ──


class TestFullSupervisionChain:
    async def test_large_loss_triggers_full_chain_response(self, chain: TradeChain):
        """Loss > $500 should: Accountant alerts → Ops halves capital → QA logs."""
        acc = Accountant(chain)
        ops = OpsManager(chain, total_capital=Decimal("100000"))
        qa = QAManager(chain)

        ops._allocations["bad-bot"] = Decimal("20000")

        await acc.start()
        await ops.start()
        await qa.start()

        # Bot reports a $800 loss
        await chain.publish(Message(
            type=MessageType.TRADE_EXECUTED,
            sender_id="bad-bot",
            payload={
                "agent_id": "bad-bot",
                "symbol": "BTC/USDT",
                "side": "sell",
                "quantity": "0.1",
                "filled_price": "59000",
                "pnl": "-800",
            },
        ))

        await asyncio.sleep(0.8)

        # Accountant tracked the loss
        assert acc._total_pnl == Decimal("-800")

        # Ops Manager halved capital and paused bot
        assert ops._allocations["bad-bot"] == Decimal("10000.00")
        assert "bad-bot" in ops._paused_bots

        # Verify the bot can't request more capital while paused
        capital_responses = []
        async def capture(msg):
            if msg.type == MessageType.CAPITAL_RESPONSE:
                capital_responses.append(msg)
        chain.subscribe_direct("bad-bot", capture)

        await chain.publish(Message(
            type=MessageType.CAPITAL_REQUEST,
            sender_id="bad-bot",
            payload={"amount": "5000"},
        ))
        await asyncio.sleep(0.3)

        await acc.stop()
        await ops.stop()
        await qa.stop()

        assert len(capital_responses) >= 1
        assert capital_responses[0].payload["approved"] is False

    async def test_multiple_bots_failing_simultaneously(self, chain: TradeChain):
        """System should handle multiple simultaneous failures gracefully."""
        qa = QAManager(chain, auto_pause_threshold=2)
        acc = Accountant(chain)

        await qa.start()
        await acc.start()

        # 5 bots all report errors at once
        tasks = []
        for i in range(5):
            for _ in range(3):
                tasks.append(chain.publish(Message(
                    type=MessageType.ERROR_REPORT,
                    sender_id=f"failing-bot-{i}",
                    payload={"agent_id": f"failing-bot-{i}", "error": "Network unreachable"},
                )))

        await asyncio.gather(*tasks)
        await asyncio.sleep(0.3)

        await qa.stop()
        await acc.stop()

        assert qa._error_patterns["network_error"] == 15
        summary = qa.get_qa_summary()
        assert summary["total_errors"] == 15
        assert len(qa._bot_error_counts) == 5

    async def test_system_recovers_after_storm(self, chain: TradeChain, registry: AgentRegistry):
        """After an error storm subsides, healthy bots keep running."""
        exchange = MockAdapter()
        acc = Accountant(chain)
        qa = QAManager(chain)

        await registry.register(acc)
        await registry.register(qa)

        class SturdyBot(TradingBot):
            def __init__(self, bot_id):
                super().__init__(
                    bot_id, "sturdy", chain, exchange,
                    symbol="BTC/USDT", loop_interval=0.05,
                )
                self.ticks = 0

            async def generate_signal(self):
                self.ticks += 1
                return Signal.HOLD

        bots = []
        for i in range(5):
            bot = SturdyBot(f"sturdy-{i}")
            bot.subscribe_to("system")
            await registry.register(bot)
            bots.append(bot)

        # Simulate error storm
        for _ in range(10):
            await chain.publish(Message(
                type=MessageType.ERROR_REPORT,
                sender_id="external-system",
                payload={"agent_id": "external-system", "error": "Database connection lost"},
            ))

        await asyncio.sleep(0.5)

        # All sturdy bots should still be running
        for bot in bots:
            assert bot.status == AgentStatus.RUNNING
            assert bot.ticks > 0
            assert bot.metrics["errors"] == 0

        await registry.stop_all()


# ── Test 7: Spam Resistance ──


class TestSpamResistance:
    async def test_message_history_bounded_under_spam(self, chain: TradeChain):
        """TradeChain history should not grow unbounded under message spam."""
        chain_bounded = TradeChain(max_history=100)

        for i in range(500):
            await chain_bounded.publish(Message(
                type=MessageType.AGENT_CHAT,
                sender_id=f"spammer-{i % 10}",
                payload={"spam": True},
            ))

        history = chain_bounded.get_history(limit=1000)
        assert len(history) <= 100

    async def test_spam_bot_doesnt_block_other_agents(self, chain: TradeChain, registry: AgentRegistry):
        """A bot flooding messages should not block others from executing."""
        exchange = MockAdapter()

        spam = SpamBot("spammer", chain, exchange)
        spam.subscribe_to("system")

        class QuietBot(TradingBot):
            def __init__(self):
                super().__init__(
                    "quiet-bot", "quiet", chain, exchange,
                    symbol="BTC/USDT", loop_interval=0.05,
                )
                self.ticks = 0

            async def generate_signal(self):
                self.ticks += 1
                return Signal.HOLD

        quiet = QuietBot()
        quiet.subscribe_to("system")

        await registry.register(spam)
        await registry.register(quiet)
        await asyncio.sleep(0.5)
        await registry.stop_all()

        assert quiet.ticks > 0
        assert spam.spam_count > 0


# ── Test 8: Graceful Shutdown ──


class TestGracefulShutdown:
    async def test_all_agents_stop_cleanly(self, chain: TradeChain, registry: AgentRegistry):
        """Registry.stop_all() should stop every agent without errors."""
        exchange = MockAdapter()
        acc = Accountant(chain)
        ops = OpsManager(chain)
        qa = QAManager(chain)

        await registry.register(acc)
        await registry.register(ops)
        await registry.register(qa)

        factory = AgentFactory(chain, registry, exchange)
        await factory.create_fleet("mean_reversion", count=10, symbols=["BTC/USDT"])

        assert registry.total_count == 13
        assert registry.active_count == 13

        await registry.stop_all()

        agents = registry.list_agents()
        for agent_status in agents:
            assert agent_status["status"] == "stopped"

    async def test_double_stop_is_safe(self, chain: TradeChain):
        """Stopping an already-stopped agent should not raise."""
        exchange = MockAdapter()

        class NullBot(TradingBot):
            async def generate_signal(self):
                return Signal.HOLD

        bot = NullBot("null-bot", "test", chain, exchange, symbol="BTC/USDT", loop_interval=0.05)
        bot.subscribe_to("system")
        await bot.start()
        await bot.stop()
        await bot.stop()  # Should not raise
        assert bot.status == AgentStatus.STOPPED
