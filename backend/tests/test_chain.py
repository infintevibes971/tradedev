import asyncio

import pytest

from app.chain.messages import Message, MessageType, Priority, TradeRequest
from app.chain.tradechain import TradeChain


@pytest.fixture
def chain():
    return TradeChain()


async def test_publish_broadcast_delivers_to_subscribers(chain: TradeChain):
    received = []

    async def handler(msg: Message):
        received.append(msg)

    chain.subscribe("bot-1", "trade", handler)
    chain.subscribe("bot-2", "trade", handler)

    await chain.publish(
        TradeRequest(
            sender_id="bot-3",
            payload={"symbol": "BTC/USDT", "side": "buy", "quantity": 0.1},
        )
    )

    assert len(received) == 2
    assert all(m.type == MessageType.TRADE_REQUEST for m in received)


async def test_sender_does_not_receive_own_broadcast(chain: TradeChain):
    received = []

    async def handler(msg: Message):
        received.append(msg)

    chain.subscribe("bot-1", "trade", handler)

    await chain.publish(
        TradeRequest(sender_id="bot-1", payload={"symbol": "ETH/USDT", "side": "sell"})
    )

    assert len(received) == 0


async def test_direct_message_reaches_only_target(chain: TradeChain):
    received_a, received_b = [], []

    async def handler_a(msg: Message):
        received_a.append(msg)

    async def handler_b(msg: Message):
        received_b.append(msg)

    chain.subscribe_direct("agent-a", handler_a)
    chain.subscribe_direct("agent-b", handler_b)

    await chain.publish(
        Message(
            type=MessageType.CAPITAL_REQUEST,
            sender_id="bot-1",
            target_id="agent-a",
            payload={"amount": 1000},
        )
    )

    assert len(received_a) == 1
    assert len(received_b) == 0


async def test_history_is_stored_and_queryable(chain: TradeChain):
    await chain.publish(
        Message(type=MessageType.AGENT_CHAT, sender_id="bot-1", payload={"text": "hello"})
    )
    await chain.publish(
        Message(type=MessageType.ERROR_REPORT, sender_id="qa", payload={"error": "timeout"})
    )

    all_history = chain.get_history()
    assert len(all_history) == 2

    agent_only = chain.get_history(topic="agent")
    assert len(agent_only) == 1

    error_only = chain.get_history(topic="error")
    assert len(error_only) == 1


async def test_history_respects_max_limit():
    chain = TradeChain(max_history=5)
    for i in range(10):
        await chain.publish(
            Message(type=MessageType.AGENT_CHAT, sender_id=f"bot-{i}", payload={})
        )

    assert len(chain.get_history(limit=100)) == 5


async def test_unsubscribe_stops_delivery(chain: TradeChain):
    received = []

    async def handler(msg: Message):
        received.append(msg)

    chain.subscribe("bot-1", "trade", handler)
    chain.subscribe_direct("bot-1", handler)
    chain.unsubscribe("bot-1")

    await chain.publish(
        TradeRequest(sender_id="bot-2", payload={"symbol": "BTC/USDT", "side": "buy"})
    )
    await chain.publish(
        Message(
            type=MessageType.AGENT_CHAT,
            sender_id="bot-2",
            target_id="bot-1",
            payload={},
        )
    )

    assert len(received) == 0


async def test_handler_error_does_not_crash_bus(chain: TradeChain):
    async def bad_handler(msg: Message):
        raise RuntimeError("boom")

    good_received = []

    async def good_handler(msg: Message):
        good_received.append(msg)

    chain.subscribe("bad-bot", "trade", bad_handler)
    chain.subscribe("good-bot", "trade", good_handler)

    await chain.publish(
        TradeRequest(sender_id="sender", payload={"symbol": "BTC/USDT", "side": "buy"})
    )

    assert len(good_received) == 1
