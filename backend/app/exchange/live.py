import logging
from decimal import Decimal
from typing import Any

from app.exchange.adapter import ExchangeAdapter

logger = logging.getLogger(__name__)


class LiveAdapter(ExchangeAdapter):
    """Live exchange adapter using ccxt. Requires valid API keys."""

    def __init__(self, exchange_id: str, api_key: str, api_secret: str, sandbox: bool = True):
        super().__init__(exchange_id)
        try:
            import ccxt.async_support as ccxt_async
        except ImportError:
            raise RuntimeError("ccxt is required for live trading: pip install ccxt")

        exchange_class = getattr(ccxt_async, exchange_id, None)
        if not exchange_class:
            raise ValueError(f"Unsupported exchange: {exchange_id}")

        self._exchange = exchange_class({
            "apiKey": api_key,
            "secret": api_secret,
            "sandbox": sandbox,
            "enableRateLimit": True,
        })
        logger.info(f"LiveAdapter initialized for {exchange_id} (sandbox={sandbox})")

    async def get_ticker(self, symbol: str) -> dict[str, Any]:
        ticker = await self._exchange.fetch_ticker(symbol)
        return {
            "bid": Decimal(str(ticker["bid"] or 0)),
            "ask": Decimal(str(ticker["ask"] or 0)),
            "last": Decimal(str(ticker["last"] or 0)),
            "volume": Decimal(str(ticker["baseVolume"] or 0)),
        }

    async def place_order(
        self, symbol: str, side: str, quantity: Decimal, price: Decimal | None = None
    ) -> dict[str, Any]:
        order_type = "limit" if price else "market"
        order = await self._exchange.create_order(
            symbol, order_type, side, float(quantity), float(price) if price else None
        )
        return {
            "id": order["id"],
            "symbol": order["symbol"],
            "side": order["side"],
            "quantity": str(order["amount"]),
            "filled_price": str(order.get("average") or order.get("price") or 0),
            "status": order["status"],
        }

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        try:
            await self._exchange.cancel_order(order_id, symbol)
            return True
        except Exception:
            logger.exception(f"Failed to cancel order {order_id}")
            return False

    async def get_balance(self) -> dict[str, Decimal]:
        balance = await self._exchange.fetch_balance()
        return {
            asset: Decimal(str(info["free"]))
            for asset, info in balance.get("total", {}).items()
            if isinstance(info, dict) and float(info.get("free", 0)) > 0
        }

    async def get_order_book(self, symbol: str, depth: int = 10) -> dict[str, list]:
        book = await self._exchange.fetch_order_book(symbol, depth)
        return {
            "bids": [[str(p), str(q)] for p, q in book["bids"][:depth]],
            "asks": [[str(p), str(q)] for p, q in book["asks"][:depth]],
        }

    async def get_ohlcv(
        self, symbol: str, timeframe: str = "1h", limit: int = 100
    ) -> list[list]:
        return await self._exchange.fetch_ohlcv(symbol, timeframe, limit=limit)

    async def close(self) -> None:
        await self._exchange.close()
