"""API routes for portfolio balance and P&L — the source of truth for the dashboard."""

from decimal import Decimal

from fastapi import APIRouter

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

# These get set by main.py at startup
_exchange = None
_registry = None


def set_exchange(exchange) -> None:
    global _exchange
    _exchange = exchange


def set_registry(registry) -> None:
    global _registry
    _registry = registry


@router.get("/balance")
async def get_balance() -> dict:
    """Real balance from the exchange adapter (mock or live).

    Returns the actual wallet state, not a hardcoded number.
    """
    if not _exchange:
        return {"error": "Exchange not initialized", "balances": {}}

    raw_balances = await _exchange.get_balance()
    balances = {asset: str(amount) for asset, amount in raw_balances.items()}

    # Calculate total in USDT terms (simplified — uses USDT as base)
    total_usdt = raw_balances.get("USDT", Decimal("0"))

    # For non-USDT assets, estimate value using ticker
    for asset, amount in raw_balances.items():
        if asset == "USDT" or amount == 0:
            continue
        symbol = f"{asset}/USDT"
        try:
            ticker = await _exchange.get_ticker(symbol)
            total_usdt += amount * ticker["last"]
        except (ValueError, KeyError):
            pass  # Unknown symbol — skip

    return {
        "balances": balances,
        "total_usdt": str(total_usdt.quantize(Decimal("0.01"))),
    }


@router.get("/summary")
async def portfolio_summary() -> dict:
    """Full portfolio summary: balance + all bot P&L + unrealized positions."""
    if not _exchange or not _registry:
        return {"error": "System not initialized"}

    # Get exchange balance
    raw_balances = await _exchange.get_balance()
    total_usdt = raw_balances.get("USDT", Decimal("0"))

    for asset, amount in raw_balances.items():
        if asset == "USDT" or amount == 0:
            continue
        symbol = f"{asset}/USDT"
        try:
            ticker = await _exchange.get_ticker(symbol)
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
                ticker = await _exchange.get_ticker(symbol)
                current_price = ticker["last"]
                if position > 0:
                    unrealized_pnl += (current_price - entry_price) * position
                else:
                    unrealized_pnl += (entry_price - current_price) * abs(position)
            except (ValueError, KeyError):
                pass

        # Per-strategy breakdown
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
        "balances": {k: str(v) for k, v in raw_balances.items()},
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
