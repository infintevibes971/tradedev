import asyncio

import pytest

from app.agents.base import AgentStatus, BaseAgent
from app.agents.registry import AgentRegistry
from app.chain.messages import Message, MessageType
from app.chain.tradechain import TradeChain


class EchoAgent(BaseAgent):
    """Test agent that counts executions and echoes messages."""

    def __init__(self, agent_id: str, chain: TradeChain):
        super().__init__(agent_id, role="test-echo", chain=chain, loop_interval=0.05)
        self.exec_count = 0
        self.received: list[Message] = []

    async def execute(self) -> None:
        self.exec_count += 1

    async def handle_message(self, message: Message) -> None:
        self.received.append(message)


@pytest.fixture
def chain():
    return TradeChain()


@pytest.fixture
def registry():
    return AgentRegistry()


async def test_agent_starts_and_executes(chain: TradeChain):
    agent = EchoAgent("echo-1", chain)
    agent.subscribe_to("agent")

    await agent.start()
    assert agent.status == AgentStatus.RUNNING

    await asyncio.sleep(0.2)
    await agent.stop()

    assert agent.status == AgentStatus.STOPPED
    assert agent.exec_count > 0
    assert agent.metrics["cycles"] > 0


async def test_agent_receives_messages(chain: TradeChain):
    agent = EchoAgent("echo-1", chain)
    agent.subscribe_to("agent")
    await agent.start()

    await chain.publish(
        Message(type=MessageType.AGENT_CHAT, sender_id="other", payload={"text": "hi"})
    )
    await asyncio.sleep(0.1)
    await agent.stop()

    assert len(agent.received) == 1
    assert agent.metrics["messages_received"] == 1


async def test_agent_pause_and_resume(chain: TradeChain):
    agent = EchoAgent("echo-1", chain)
    await agent.start()
    await asyncio.sleep(0.15)
    count_before_pause = agent.exec_count

    agent.pause()
    assert agent.status == AgentStatus.PAUSED
    await asyncio.sleep(0.15)
    count_during_pause = agent.exec_count

    assert count_during_pause == count_before_pause

    agent.resume()
    await asyncio.sleep(0.7)
    await agent.stop()

    assert agent.exec_count > count_during_pause


async def test_registry_lifecycle(chain: TradeChain, registry: AgentRegistry):
    agent1 = EchoAgent("echo-1", chain)
    agent2 = EchoAgent("echo-2", chain)

    await registry.register(agent1)
    await registry.register(agent2)

    assert registry.total_count == 2
    assert registry.active_count == 2

    agents_list = registry.list_agents()
    assert len(agents_list) == 2

    await registry.remove("echo-1")
    assert registry.total_count == 1
    assert agent1.status == AgentStatus.STOPPED

    await registry.stop_all()
    assert agent2.status == AgentStatus.STOPPED


async def test_registry_rejects_duplicate(chain: TradeChain, registry: AgentRegistry):
    agent = EchoAgent("echo-1", chain)
    await registry.register(agent)

    with pytest.raises(ValueError, match="already registered"):
        duplicate = EchoAgent("echo-1", chain)
        await registry.register(duplicate)

    await registry.stop_all()


async def test_agent_error_recovery(chain: TradeChain):
    error_reports = []

    async def capture_errors(msg: Message):
        if msg.type == MessageType.ERROR_REPORT:
            error_reports.append(msg)

    chain.subscribe("monitor", "error", capture_errors)

    class FailOnceAgent(BaseAgent):
        def __init__(self):
            super().__init__("fail-bot", "test-fail", chain, loop_interval=0.05)
            self.call_count = 0

        async def execute(self):
            self.call_count += 1
            if self.call_count == 1:
                raise RuntimeError("first run explodes")

        async def handle_message(self, message: Message):
            pass

    agent = FailOnceAgent()
    await agent.start()
    await asyncio.sleep(6.0)
    await agent.stop()

    assert agent.call_count >= 2
    assert agent.metrics["errors"] >= 1
    assert len(error_reports) >= 1
