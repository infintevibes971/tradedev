import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.agents.accountant import Accountant
from app.agents.factory import AgentFactory
from app.agents.ops_manager import OpsManager
from app.agents.qa_manager import QAManager
from app.agents.registry import AgentRegistry
from app.api.routes_agents import router as agents_router
from app.api.routes_agents import set_factory
from app.api.routes_ai import router as ai_router
from app.api.routes_portfolio import router as portfolio_router
from app.api.routes_portfolio import set_exchange_manager, set_registry as set_portfolio_registry
from app.api.routes_users import router as users_router
from app.chain.tradechain import TradeChain
from app.config import settings
from app.exchange.manager import ExchangeManager
from app.models.database import init_db
from app.websocket.manager import ConnectionManager

logging.basicConfig(level=settings.log_level, format="%(name)s | %(levelname)s | %(message)s")

chain = TradeChain()
registry = AgentRegistry()
ws_manager = ConnectionManager()

chain.on_ws_message(ws_manager.broadcast_message)


exchange_manager = ExchangeManager()
factory = AgentFactory(chain, registry, exchange_manager.active, exchange_manager=exchange_manager)
set_factory(factory)
set_exchange_manager(exchange_manager)
set_portfolio_registry(registry)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    accountant = Accountant(chain)
    ops = OpsManager(chain)
    qa = QAManager(chain)
    await registry.register(accountant)
    await registry.register(ops)
    await registry.register(qa)

    # Auto-spawn a starter fleet so the dashboard shows live trading activity
    # immediately — bots run on paper mode until a live exchange is connected
    starter_fleet = [
        {"strategy": "mean_reversion", "symbol": "BTC/USDT"},
        {"strategy": "momentum", "symbol": "BTC/USDT"},
        {"strategy": "momentum", "symbol": "ETH/USDT"},
        {"strategy": "grid", "symbol": "BTC/USDT"},
        {"strategy": "sentiment", "symbol": "SOL/USDT"},
    ]
    for bot_config in starter_fleet:
        try:
            await factory.create_bot(**bot_config, autostart=True)
        except Exception as e:
            logging.warning(f"Failed to spawn starter bot: {e}")

    bot_count = registry.active_count
    logging.info(
        f"{settings.app_name} starting — TradeChain online, DB ready, "
        f"{bot_count} agents active ({bot_count - 3} trading bots)"
    )
    yield
    await registry.stop_all()
    await exchange_manager.close_all()
    logging.info(f"{settings.app_name} shutting down — all agents stopped")


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:8000",
        "*",  # Railway/production — tighten after custom domain is set
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(users_router, prefix="/api")
app.include_router(agents_router, prefix="/api")
app.include_router(ai_router, prefix="/api")
app.include_router(portfolio_router, prefix="/api")


@app.get("/health")
async def health_check() -> dict:
    from app.ai.registry import get_mode, is_available

    return {
        "status": "online",
        "company": settings.app_name,
        "agents_active": registry.active_count,
        "agents_total": registry.total_count,
        "ws_clients": ws_manager.client_count,
        "ai_available": is_available(),
        "ai_mode": get_mode(),
    }


@app.get("/agents")
async def list_agents(role: str | None = None) -> list[dict]:
    return registry.list_agents(role=role)


@app.get("/chain/history")
async def chain_history(topic: str | None = None, limit: int = 50) -> list[dict]:
    messages = chain.get_history(topic=topic, limit=limit)
    return [m.model_dump(mode="json") for m in messages]


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


# ── Serve built frontend in production ─────────────────────
# In production, Vite builds to /app/static. FastAPI serves it
# so one container handles both API + UI — no reverse proxy needed.
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str) -> FileResponse:
        """Catch-all: serve index.html for any non-API route (SPA client routing)."""
        file_path = STATIC_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(STATIC_DIR / "index.html")
