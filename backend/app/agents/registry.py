import logging

from app.agents.base import AgentStatus, BaseAgent

logger = logging.getLogger(__name__)


class AgentRegistry:
    """Tracks all live agents and provides lifecycle operations."""

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    async def register(self, agent: BaseAgent, autostart: bool = True) -> None:
        if agent.agent_id in self._agents:
            raise ValueError(f"Agent '{agent.agent_id}' already registered")
        self._agents[agent.agent_id] = agent
        logger.info(f"Registered agent: {agent.agent_id} ({agent.role})")
        if autostart:
            await agent.start()

    async def remove(self, agent_id: str) -> None:
        agent = self._agents.pop(agent_id, None)
        if agent:
            await agent.stop()
            logger.info(f"Removed agent: {agent_id}")

    async def stop_all(self) -> None:
        for agent in list(self._agents.values()):
            await agent.stop()
        logger.info(f"Stopped all {len(self._agents)} agents")

    def get(self, agent_id: str) -> BaseAgent | None:
        return self._agents.get(agent_id)

    def list_agents(self, role: str | None = None) -> list[dict]:
        agents = self._agents.values()
        if role:
            agents = [a for a in agents if a.role == role]
        return [a.get_status() for a in agents]

    def get_by_role(self, role: str) -> list[BaseAgent]:
        return [a for a in self._agents.values() if a.role == role]

    @property
    def active_count(self) -> int:
        return sum(1 for a in self._agents.values() if a.status == AgentStatus.RUNNING)

    @property
    def total_count(self) -> int:
        return len(self._agents)
