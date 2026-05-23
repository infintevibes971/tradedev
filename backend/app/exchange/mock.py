import random
import uuid
from decimal import Decimal
from typing import Any

from app.exchange.adapter import ExchangeAdapter

MOCK_PRICES: dict[str, Decimal] = {
    "BTC/USDT": Decimal("67500.00"),
    "ETH/USDT": Decimal("3450.00"),
    "SOL/USDT": Decimal("172.50"),
    "BNB/USDT": Decimal("610.00"),
    "XRP/USDT": Decimal("0.5200"),
    "ADA/USDT": Decimal("0.4500"),
    "DOGE/USDT": Decimal("0.1250"),
    "AVAX/USDT": Decimal("38.00"),
    "DOT/USDT": Decimal("7.50"),
    "LINK/USDT": Decimal("14.80"),
}


class MockAdapter(ExchangeAdapter):
    """Paper trading adapter with simulated prices and order fills."""

    def __init__(self) -> None:
        super().__init__("mock")
        self._balances: dict[str, Decimal] = {
            "USDT": Decimal("100000.00"),
            "BTC": Decimal("0"),
            "ETH": Decimal("0"),
        }
        self._orders: dict[str, dict] = {}
        self._price_jitter = Decimal("0.005")

    def _jitter_price(self, base_price: Decimal) -> Decimal:
        pct = Decimal(str(random.uniform(-float(self._price_jitter), float(self._price_jitter))))
        return (base_price * (1 + pct)).quantize(Decimal("0.01"))

    def _get_base_price(self, symbol: str) -> Decimal:
        if symbol not in MOCK_PRICES:
            raise ValueError(f"Unknown mock symbol: {symbol}")
        return MOCK_PRICES[symbol]

    async def get_ticker(self, symbol: str) -> dict[str, Any]:
        base = self._get_base_price(symbol)
        last = self._jitter_price(base)
        spread = base * Decimal("0.001")
        return {
            "bid": last - spread,
            "ask": last + spread,
            "last": last,
            "volume": Decimal(str(random.uniform(1000, 50000))).quantize(Decimal("0.01")),
        }

    async def place_order(
        self, symbol: str, side: str, quantity: Decimal, price: Decimal | None = None
    ) -> dict[str, Any]:
        if side not in ("buy", "sell"):
            raise ValueError(f"Invalid side: {side}")

        ticker = await self.get_ticker(symbol)
        fill_price = price or (ticker["ask"] if side == "buy" else ticker["bid"])
        cost = fill_price * quantity
        base_asset = symbol.split("/")[0]
        quote_asset = symbol.split("/")[1]

        if side == "buy":
            if self._balances.get(quote_asset, Decimal("0")) < cost:
                return {"id": None, "status": "rejected", "reason": "insufficient_balance"}
            self._balances[quote_asset] = self._balances.get(quote_asset, Decimal("0")) - cost
            self._balances[base_asset] = self._balances.get(base_asset, Decimal("0")) + quantity
        else:
            if self._balances.get(base_asset, Decimal("0")) < quantity:
                return {"id": None, "status": "rejected", "reason": "insufficient_balance"}
            self._balances[base_asset] = self._balances.get(base_asset, Decimal("0")) - quantity
            self._balances[quote_asset] = self._balances.get(quote_asset, Decimal("0")) + cost

        order_id = uuid.uuid4().hex[:10]
        order = {
            "id": order_id,
            "symbol": symbol,
            "side": side,
            "quantity": str(quantity),
            "filled_price": str(fill_price),
            "cost": str(cost),
            "status": "filled",
        }
        self._orders[order_id] = order
        return order

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        order = self._orders.get(order_id)
        if order and order["status"] == "open":
            order["status"] = "cancelled"
            return True
        return False

    async def get_balance(self) -> dict[str, Decimal]:
        return {k: v for k, v in self._balances.items() if v > 0}

    async def get_order_book(self, symbol: str, depth: int = 10) -> dict[str, list]:
        base = self._get_base_price(symbol)
        bids, asks = [], []
        for i in range(depth):
            offset = base * Decimal(str(0.0005 * (i + 1)))
            qty = Decimal(str(random.uniform(0.1, 5.0))).quantize(Decimal("0.0001"))
            bids.append([str(base - offset), str(qty)])
            asks.append([str(base + offset), str(qty)])
        return {"bids": bids, "asks": asks}

    async def get_ohlcv(
        self, symbol: str, timeframe: str = "1h", limit: int = 100
    ) -> list[list]:
        base = float(self._get_base_price(symbol))
        candles = []
        for i in range(limit):
            ts = 1700000000 + i * 3600
            o = base * random.uniform(0.99, 1.01)
            c = base * random.uniform(0.99, 1.01)
            h = max(o, c) * random.uniform(1.0, 1.005)
            low = min(o, c) * random.uniform(0.995, 1.0)
            vol = random.uniform(100, 10000)
            candles.append([ts, round(o, 2), round(h, 2), round(low, 2), round(c, 2), round(vol, 2)])
        return candles
