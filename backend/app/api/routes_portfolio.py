"""API routes for portfolio balance and P&L — the source of truth for the dashboard.

Queries the REAL exchange balance (OKX, Binance, etc.) via ExchangeManager,
not hardcoded numbers.
"""

from decimal import Decimal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

# Set by main.py at startup
_exchange_manager = None
_registry = None


def set_exchange_manager(manager) -> None:
    global _exchange_manager
    _exchange_manager = manager


def set_registry(registry) -> None:
    global _registry
    _registry = registry


@router.get("/balance")
async def get_balance() -> dict:
    """Real balance from the active exchange (OKX, Binance, or paper)."""
    if not _exchange_manager:
        return {"error": "Exchange manager not initialized", "balances": {}}

    try:
        raw_balances = await _exchange_manager.get_active_balance()
    except Exception as e:
        return {"error": str(e), "balances": {}}

    balances = {asset: str(amount) for asset, amount in raw_balances.items()}

    # Calculate total in USDT terms
    total_usdt = raw_balances.get("USDT", Decimal("0"))
    for asset, amount in raw_balances.items():
        if asset in ("USDT", "USD") or amount == 0:
            continue
        symbol = f"{asset}/USDT"
        try:
            ticker = await _exchange_manager.active.get_ticker(symbol)
            total_usdt += amount * ticker["last"]
        except (ValueError, KeyError):
            pass

    return {
        "balances": balances,
        "total_usdt": str(total_usdt.quantize(Decimal("0.01"))),
        "exchange": _exchange_manager.active_name,
        "is_live": _exchange_manager.is_live,
    }


@router.get("/summary")
async def portfolio_summary() -> dict:
    """Full portfolio summary with real exchange data."""
    if not _exchange_manager or not _registry:
        return {"error": "System not initialized"}

    # Get real balance from active exchange
    try:
        raw_balances = await _exchange_manager.get_active_balance()
    except Exception as e:
        raw_balances = {}

    total_usdt = Decimal("0")
    if isinstance(raw_balances, dict):
        total_usdt = raw_balances.get("USDT", Decimal("0"))
        for asset, amount in raw_balances.items():
            if asset in ("USDT", "USD") or amount == 0:
                continue
            symbol = f"{asset}/USDT"
            try:
                ticker = await _exchange_manager.active.get_ticker(symbol)
                total_usdt += amount * ticker["last"]
            except (ValueError, KeyError):
                pass

    # Get bot stats
    agents = _registry.list_agents()
    traders = [a for a in agents if a.get("role", "").startswith("trader:")]

    realized_pnl = Decimal("0")
    unrealized_pnl = Decimal("0")
    total_trades = 0
    open_positions = 0
    strategies: dict[str, dict] = {}

    for t in traders:
        rpnl = Decimal(str(t.get("realized_pnl", "0")))
        realized_pnl += rpnl
        total_trades += t.get("total_trades", 0)

        position = Decimal(str(t.get("position", "0")))
        entry_price = Decimal(str(t.get("entry_price", "0")))

        if position != 0 and entry_price != 0:
            open_positions += 1
            symbol = t.get("symbol", "BTC/USDT")
            try:
                ticker = await _exchange_manager.active.get_ticker(symbol)
                current_price = ticker["last"]
                if position > 0:
                    unrealized_pnl += (current_price - entry_price) * position
                else:
                    unrealized_pnl += (entry_price - current_price) * abs(position)
            except (ValueError, KeyError):
                pass

        strat = t.get("strategy", "unknown")
        if strat not in strategies:
            strategies[strat] = {"count": 0, "pnl": Decimal("0"), "trades": 0, "positions": 0}
        strategies[strat]["count"] += 1
        strategies[strat]["pnl"] += rpnl
        strategies[strat]["trades"] += t.get("total_trades", 0)
        if position != 0:
            strategies[strat]["positions"] += 1

    return {
        "total_balance_usdt": str(total_usdt.quantize(Decimal("0.01"))),
        "realized_pnl": str(realized_pnl.quantize(Decimal("0.01"))),
        "unrealized_pnl": str(unrealized_pnl.quantize(Decimal("0.01"))),
        "total_pnl": str((realized_pnl + unrealized_pnl).quantize(Decimal("0.01"))),
        "total_trades": total_trades,
        "open_positions": open_positions,
        "active_bots": len(traders),
        "balances": {k: str(v) for k, v in raw_balances.items()} if isinstance(raw_balances, dict) else {},
        "exchange": _exchange_manager.active_name,
        "is_live": _exchange_manager.is_live,
        "strategies": {
            name: {
                "count": s["count"],
                "pnl": str(s["pnl"].quantize(Decimal("0.01"))),
                "trades": s["trades"],
                "positions": s["positions"],
            }
            for name, s in strategies.items()
        },
    }


@router.get("/exchanges")
async def list_exchanges() -> dict:
    """Show all connected exchanges and which is active."""
    if not _exchange_manager:
        return {"error": "Exchange manager not initialized"}
    return _exchange_manager.get_status()


@router.get("/all-balances")
async def all_balances() -> dict:
    """Get balances from ALL connected exchanges (paper + live)."""
    if not _exchange_manager:
        return {"error": "Exchange manager not initialized"}
    return {"exchanges": await _exchange_manager.get_all_balances()}


class ConnectRequest(BaseModel):
    user_id: str


@router.post("/connect")
async def connect_exchanges(body: ConnectRequest) -> dict:
    """Load and connect all stored API keys for a user.

    Call this after login to activate live exchange connections.
    """
    if not _exchange_manager:
        raise HTTPException(503, "Exchange manager not initialized")

    results = await _exchange_manager.load_user_keys(body.user_id)

    # Auto-switch to first successful live connection
    connected = [r for r in results if r["status"] == "connected" and not r["is_paper"]]
    if connected:
        await _exchange_manager.switch_to_live(connected[0]["id"])

    # If only paper connections, still switch to first one
    if not connected:
        paper = [r for r in results if r["status"] == "connected"]
        if paper:
            await _exchange_manager.switch_to_live(paper[0]["id"])

    return {
        "connections": results,
        "active": _exchange_manager.get_status(),
    }


class SwitchRequest(BaseModel):
    key_id: str | None = None  # None = switch to paper


@router.post("/switch")
async def switch_exchange(body: SwitchRequest) -> dict:
    """Switch which exchange is active for trading and balance display."""
    if not _exchange_manager:
        raise HTTPException(503, "Exchange manager not initialized")

    if body.key_id is None:
        _exchange_manager.switch_to_paper()
    else:
        ok = await _exchange_manager.switch_to_live(body.key_id)
        if not ok:
            raise HTTPException(
                400,
                "Exchange not connected. Call /api/portfolio/connect first.",
            )

    return _exchange_manager.get_status()
