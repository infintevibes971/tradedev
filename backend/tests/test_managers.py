import asyncio
from decimal import Decimal

import pytest

from app.agents.accountant import Accountant
from app.agents.ops_manager import OpsManager
from app.agents.qa_manager import QAManager
from app.chain.messages import Message, MessageType, Priority
from app.chain.tradechain import TradeChain


@pytest.fixture
def chain():
    return TradeChain()


# ── Accountant Tests ──


class TestAccountant:
    async def test_records_trade_and_updates_pnl(self, chain: TradeChain):
        acc = Accountant(chain)
        await acc.start()

        await chain.publish(Message(
            type=MessageType.TRADE_EXECUTED,
            sender_id="bot-1",
            payload={
                "agent_id": "bot-1",
                "symbol": "BTC/USDT",
                "side": "buy",
                "quantity": "0.1",
                "filled_price": "67000",
                "pnl": "150.00",
            },
        ))
        await asyncio.sleep(0.1)
        await acc.stop()

        assert acc._total_pnl == Decimal("150.00")
        assert acc._bot_trade_count["bot-1"] == 1
        assert acc._bot_wins["bot-1"] == 1

    async def test_tracks_losses(self, chain: TradeChain):
        acc = Accountant(chain)
        await acc.start()

        await chain.publish(Message(
            type=MessageType.TRADE_EXECUTED,
            sender_id="bot-1",
            payload={"agent_id": "bot-1", "symbol": "ETH/USDT", "pnl": "-200"},
        ))
        await asyncio.sleep(0.1)
        await acc.stop()

        assert acc._total_pnl == Decimal("-200")
        assert acc.get_win_rate("bot-1") == 0.0

    async def test_large_loss_triggers_risk_alert(self, chain: TradeChain):
        risk_alerts = []

        async def capture(msg: Message):
            if msg.type == MessageType.RISK_ALERT:
                risk_alerts.append(msg)

        chain.subscribe("monitor", "risk", capture)

        acc = Accountant(chain)
        await acc.start()

        await chain.publish(Message(
            type=MessageType.TRADE_EXECUTED,
            sender_id="bot-1",
            payload={"agent_id": "bot-1", "symbol": "BTC/USDT", "pnl": "-600"},
        ))
        await asyncio.sleep(0.2)
        await acc.stop()

        assert len(risk_alerts) >= 1
        assert risk_alerts[0].payload["alert"] == "large_loss"

    async def test_generate_report(self, chain: TradeChain):
        acc = Accountant(chain)
        await acc.start()

        for i in range(3):
            pnl = "100" if i % 2 == 0 else "-50"
            await chain.publish(Message(
                type=MessageType.TRADE_EXECUTED,
                sender_id="bot-1",
                payload={"agent_id": "bot-1", "symbol": "BTC/USDT", "pnl": pnl},
            ))
        await asyncio.sleep(0.1)
        await acc.stop()

        report = acc.generate_report()
        assert report["total_trades"] == 3
        assert report["active_bots"] == 1
        assert "bot-1" in report["bot_summaries"]

    async def test_win_rate_calculation(self, chain: TradeChain):
        acc = Accountant(chain)
        await acc.start()

        for pnl in ["100", "-50", "200", "75"]:
            await chain.publish(Message(
                type=MessageType.TRADE_EXECUTED,
                sender_id="bot-1",
                payload={"agent_id": "bot-1", "pnl": pnl},
            ))
        await asyncio.sleep(0.1)
        await acc.stop()

        assert acc.get_win_rate("bot-1") == 0.75


# ── Ops Manager Tests ──


class TestOpsManager:
    async def test_capital_request_within_limits(self, chain: TradeChain):
        responses = []

        async def capture(msg: Message):
            if msg.type == MessageType.CAPITAL_RESPONSE:
                responses.append(msg)

        chain.subscribe_direct("bot-1", capture)

        ops = OpsManager(chain, total_capital=Decimal("100000"))
        acc = Accountant(chain)
        await ops.start()
        await acc.start()

        await chain.publish(Message(
            type=MessageType.CAPITAL_REQUEST,
            sender_id="bot-1",
            payload={"amount": "5000"},
        ))
        await asyncio.sleep(0.3)
        await ops.stop()
        await acc.stop()

        assert len(responses) >= 1

    async def test_paused_bot_denied_capital(self, chain: TradeChain):
        responses = []

        async def capture(msg: Message):
            if msg.type == MessageType.CAPITAL_RESPONSE:
                responses.append(msg)

        chain.subscribe_direct("bot-1", capture)

        ops = OpsManager(chain)
        ops._paused_bots.add("bot-1")
        await ops.start()

        await chain.publish(Message(
            type=MessageType.CAPITAL_REQUEST,
            sender_id="bot-1",
            payload={"amount": "5000"},
        ))
        await asyncio.sleep(0.2)
        await ops.stop()

        assert len(responses) >= 1
        assert responses[0].payload["approved"] is False

    async def test_risk_alert_halves_allocation(self, chain: TradeChain):
        ops = OpsManager(chain)
        ops._allocations["bot-1"] = Decimal("10000")
        await ops.start()

        await chain.publish(Message(
            type=MessageType.RISK_ALERT,
            sender_id="accountant",
            payload={"alert": "large_loss", "agent_id": "bot-1"},
            priority=Priority.HIGH,
        ))
        await asyncio.sleep(0.2)
        await ops.stop()

        assert ops._allocations["bot-1"] == Decimal("5000.00")
        assert "bot-1" in ops._paused_bots

    async def test_ops_summary(self, chain: TradeChain):
        ops = OpsManager(chain, total_capital=Decimal("50000"))
        ops._allocations["bot-1"] = Decimal("10000")
        ops._allocations["bot-2"] = Decimal("5000")

        summary = ops.get_ops_summary()
        assert summary["total_capital"] == "50000"
        assert summary["allocated"] == "15000"
        assert summary["available"] == "35000"


# ── QA Manager Tests ──


class TestQAManager:
    async def test_processes_error_report(self, chain: TradeChain):
        qa = QAManager(chain)
        await qa.start()

        await chain.publish(Message(
            type=MessageType.ERROR_REPORT,
            sender_id="bot-1",
            payload={"agent_id": "bot-1", "error": "Connection timeout on API call"},
        ))
        await asyncio.sleep(0.1)
        await qa.stop()

        assert qa._bot_error_counts["bot-1"] == 1
        assert qa._error_patterns["api_timeout"] == 1

    async def test_classifies_error_types(self, chain: TradeChain):
        qa = QAManager(chain)

        assert qa._classify_error("Connection timeout") == "api_timeout"
        assert qa._classify_error("429 Too Many Requests") == "rate_limit"
        assert qa._classify_error("Insufficient balance") == "insufficient_funds"
        assert qa._classify_error("Network unreachable") == "network_error"
        assert qa._classify_error("401 Unauthorized") == "auth_error"
        assert qa._classify_error("Something weird") == "unknown"

    async def test_diagnoses_known_errors(self, chain: TradeChain):
        qa = QAManager(chain)
        await qa.start()

        await chain.publish(Message(
            type=MessageType.ERROR_REPORT,
            sender_id="bot-1",
            payload={"agent_id": "bot-1", "error": "Rate limit exceeded (429)"},
        ))
        await asyncio.sleep(0.1)
        await qa.stop()

        assert len(qa._diagnosed_issues) == 1
        assert qa._diagnosed_issues[0]["auto_resolved"] is True

    async def test_auto_pause_on_threshold(self, chain: TradeChain):
        pause_requests = []

        async def capture(msg: Message):
            if msg.type == MessageType.SYSTEM_COMMAND:
                pause_requests.append(msg)

        chain.subscribe_direct("ops-manager", capture)

        qa = QAManager(chain, auto_pause_threshold=3)
        await qa.start()

        for _ in range(3):
            await chain.publish(Message(
                type=MessageType.ERROR_REPORT,
                sender_id="bot-1",
                payload={"agent_id": "bot-1", "error": "generic error"},
            ))
            await asyncio.sleep(0.05)

        await asyncio.sleep(0.2)
        await qa.stop()

        assert len(pause_requests) >= 1
        assert pause_requests[0].payload["command"] == "pause_bot"

    async def test_validates_trade_anomalies(self, chain: TradeChain):
        qa = QAManager(chain)
        await qa.start()

        await chain.publish(Message(
            type=MessageType.TRADE_EXECUTED,
            sender_id="bot-1",
            payload={
                "quantity": "0",
                "filled_price": "67000",
                "symbol": "BTC/USDT",
            },
        ))
        await asyncio.sleep(0.1)
        await qa.stop()

        anomalies = [
            d for d in qa._diagnosed_issues
            if "trade_anomaly" in d.get("error_type", "")
        ]
        assert len(anomalies) >= 1

    async def test_qa_summary(self, chain: TradeChain):
        qa = QAManager(chain)
        await qa.start()

        await chain.publish(Message(
            type=MessageType.ERROR_REPORT,
            sender_id="bot-1",
            payload={"agent_id": "bot-1", "error": "timeout"},
        ))
        await chain.publish(Message(
            type=MessageType.ERROR_REPORT,
            sender_id="bot-2",
            payload={"agent_id": "bot-2", "error": "network error"},
        ))
        await asyncio.sleep(0.1)
        await qa.stop()

        summary = qa.get_qa_summary()
        assert summary["total_errors"] == 2
        assert "api_timeout" in summary["error_patterns"]
        assert "network_error" in summary["error_patterns"]


# ── Integration: All Three Managers Working Together ──


async def test_full_management_workflow(chain: TradeChain):
    """Simulate: bot trades -> accountant tracks -> large loss ->
    risk alert -> ops halves capital -> qa logs the pattern."""
    acc = Accountant(chain)
    ops = OpsManager(chain, total_capital=Decimal("100000"))
    qa = QAManager(chain)

    ops._allocations["bot-1"] = Decimal("20000")

    await acc.start()
    await ops.start()
    await qa.start()

    await chain.publish(Message(
        type=MessageType.TRADE_EXECUTED,
        sender_id="bot-1",
        payload={"agent_id": "bot-1", "symbol": "BTC/USDT", "pnl": "100"},
    ))
    await asyncio.sleep(0.1)

    await chain.publish(Message(
        type=MessageType.TRADE_EXECUTED,
        sender_id="bot-1",
        payload={"agent_id": "bot-1", "symbol": "BTC/USDT", "pnl": "-700"},
    ))
    await asyncio.sleep(0.3)

    await acc.stop()
    await ops.stop()
    await qa.stop()

    assert acc._total_pnl == Decimal("-600")
    assert "bot-1" in ops._paused_bots
    assert ops._allocations["bot-1"] == Decimal("10000.00")

    report = acc.generate_report()
    assert report["total_trades"] == 2
