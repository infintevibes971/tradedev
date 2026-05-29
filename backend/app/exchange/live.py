import asyncio
import logging
from decimal import Decimal
from typing import Any

from app.exchange.adapter import ExchangeAdapter

logger = logging.getLogger(__name__)

# Timeout for any single exchange API call (seconds)
API_TIMEOUT = 15


class LiveAdapter(ExchangeAdapter):
    """Live exchange adapter using ccxt. Requires valid API keys."""

    def __init__(
        self,
        exchange_id: str,
        api_key: str,
        api_secret: str,
        passphrase: str | None = None,
        sandbox: bool = False,
    ):
        super().__init__(exchange_id)
        try:
            import ccxt.async_support as ccxt_async
        except ImportError:
            raise RuntimeError("ccxt is required for live trading: pip install ccxt")

        exchange_class = getattr(ccxt_async, exchange_id, None)
        if not exchange_class:
            raise ValueError(f"Unsupported exchange: {exchange_id}")

        config: dict = {
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
            "timeout": API_TIMEOUT * 1000,  # ccxt uses milliseconds
        }
        # Only enable sandbox if explicitly requested — real trading by default
        if sandbox:
            config["sandbox"] = True
        # OKX and some others require a passphrase
        if passphrase:
            config["password"] = passphrase

        self._exchange = exchange_class(config)
        logger.info(f"LiveAdapter initialized for {exchange_id} (sandbox={sandbox})")

    async def get_ticker(self, symbol: str) -> dict[str, Any]:
        try:
            ticker = await asyncio.wait_for(
                self._exchange.fetch_ticker(symbol), timeout=API_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.warning("Ticker timeout for %s on %s", symbol, self.exchange_id)
            raise ValueError(f"Ticker timeout: {symbol}")
        except Exception as e:
            logger.warning("Ticker error for %s on %s: %s", symbol, self.exchange_id, e)
            raise

        return {
            "bid": Decimal(str(ticker.get("bid") or 0)),
            "ask": Decimal(str(ticker.get("ask") or 0)),
            "last": Decimal(str(ticker.get("last") or 0)),
            "volume": Decimal(str(ticker.get("baseVolume") or 0)),
            "change_24h": Decimal(str(ticker.get("percentage") or 0)),
            "volume_24h": Decimal(str(ticker.get("quoteVolume") or 0)),
        }

    async def place_order(
        self, symbol: str, side: str, quantity: Decimal, price: Decimal | None = None
    ) -> dict[str, Any]:
        order_type = "limit" if price else "market"
        logger.info(
            "Placing %s %s order: %s %s on %s",
            order_type, side, quantity, symbol, self.exchange_id,
        )
        try:
            order = await asyncio.wait_for(
                self._exchange.create_order(
                    symbol, order_type, side, float(quantity),
                    float(price) if price else None,
                ),
                timeout=API_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.error("Order timeout: %s %s %s on %s", side, quantity, symbol, self.exchange_id)
            return {"id": None, "status": "rejected", "reason": "timeout"}
        except Exception as e:
            logger.error("Order failed: %s %s %s — %s", side, quantity, symbol, e)
            return {"id": None, "status": "rejected", "reason": str(e)}

        logger.info("Order filled: %s", order.get("id"))
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
        """Fetch real balance from exchange via ccxt.

        ccxt.fetch_balance() returns:
          {"free": {"BTC": 0.5, "USDT": 1000}, "total": {"BTC": 0.5, ...}, ...}

        "free" = available to trade (not locked in orders).
        "total" entries are plain floats, NOT dicts.
        """
        try:
            balance = await asyncio.wait_for(
                self._exchange.fetch_balance(), timeout=API_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.warning("Balance timeout on %s", self.exchange_id)
            return {}
        except Exception as e:
            logger.warning("Balance error on %s: %s", self.exchange_id, e)
            return {}
        result: dict[str, Decimal] = {}

        # "free" gives us the available (non-locked) balance per asset
        free = balance.get("free", {})
        if isinstance(free, dict):
            for asset, amount in free.items():
                try:
                    val = Decimal(str(amount))
                    if val > 0:
                        result[asset] = val
                except (ValueError, TypeError):
                    continue

        # Fallback: if "free" was empty, try "total"
        if not result:
            total = balance.get("total", {})
            if isinstance(total, dict):
                for asset, amount in total.items():
                    try:
                        val = Decimal(str(amount))
                        if val > 0:
                            result[asset] = val
                    except (ValueError, TypeError):
                        continue

        return result

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
