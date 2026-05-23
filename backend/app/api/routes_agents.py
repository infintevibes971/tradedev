from decimal import Decimal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents.factory import AgentFactory

router = APIRouter(prefix="/agents", tags=["agents"])

_factory: AgentFactory | None = None


def set_factory(factory: AgentFactory) -> None:
    global _factory
    _factory = factory


def _get_factory() -> AgentFactory:
    if _factory is None:
        raise HTTPException(503, "Agent factory not initialized")
    return _factory


class SpawnRequest(BaseModel):
    strategy: str
    symbol: str = "BTC/USDT"
    trade_size: float = 0.01
    count: int = 1


class FleetConfig(BaseModel):
    fleet: list[dict]


@router.get("/strategies")
async def list_strategies() -> list[dict]:
    return AgentFactory.list_strategies()


@router.post("/spawn")
async def spawn_bot(body: SpawnRequest) -> dict:
    factory = _get_factory()
    try:
        if body.count == 1:
            bot = await factory.create_bot(
                strategy=body.strategy,
                symbol=body.symbol,
                trade_size=Decimal(str(body.trade_size)),
            )
            return {"spawned": [bot.get_status()]}
        else:
            bots = await factory.create_fleet(
                strategy=body.strategy,
                count=body.count,
                symbols=[body.symbol],
            )
            return {"spawned": [b.get_status() for b in bots]}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/spawn/fleet")
async def spawn_fleet(body: FleetConfig) -> dict:
    factory = _get_factory()
    try:
        bots = await factory.create_mixed_fleet(body.fleet)
        return {"spawned": len(bots), "bots": [b.get_status() for b in bots]}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{agent_id}/pause")
async def pause_agent(agent_id: str) -> dict:
    factory = _get_factory()
    agent = factory.registry.get(agent_id)
    if not agent:
        raise HTTPException(404, f"Agent '{agent_id}' not found")
    agent.pause()
    return {"status": agent.get_status()}


@router.post("/{agent_id}/resume")
async def resume_agent(agent_id: str) -> dict:
    factory = _get_factory()
    agent = factory.registry.get(agent_id)
    if not agent:
        raise HTTPException(404, f"Agent '{agent_id}' not found")
    agent.resume()
    return {"status": agent.get_status()}


@router.delete("/{agent_id}")
async def stop_agent(agent_id: str) -> dict:
    factory = _get_factory()
    agent = factory.registry.get(agent_id)
    if not agent:
        raise HTTPException(404, f"Agent '{agent_id}' not found")
    await factory.registry.remove(agent_id)
    return {"stopped": agent_id}
