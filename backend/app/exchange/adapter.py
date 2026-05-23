from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any


class ExchangeAdapter(ABC):
    """Abstract interface for exchange interactions.

    All trading bots interact with exchanges exclusively through this interface.
    Implementations: MockAdapter (paper trading), LiveAdapter (real exchange via ccxt).
    """

    def __init__(self, exchange_id: str) -> None:
        self.exchange_id = exchange_id

    @abstractmethod
    async def get_ticker(self, symbol: str) -> dict[str, Any]:
        """Returns {"bid": Decimal, "ask": Decimal, "last": Decimal, "volume": Decimal}."""

    @abstractmethod
    async def place_order(
        self, symbol: str, side: str, quantity: Decimal, price: Decimal | None = None
    ) -> dict[str, Any]:
        """Place a limit or market order. Returns order dict with id, status, filled_price."""

    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an open order. Returns True if cancelled."""

    @abstractmethod
    async def get_balance(self) -> dict[str, Decimal]:
        """Returns {asset: available_balance} mapping."""

    @abstractmethod
    async def get_order_book(self, symbol: str, depth: int = 10) -> dict[str, list]:
        """Returns {"bids": [[price, qty], ...], "asks": [[price, qty], ...]}."""

    @abstractmethod
    async def get_ohlcv(
        self, symbol: str, timeframe: str = "1h", limit: int = 100
    ) -> list[list]:
        """Returns [[timestamp, open, high, low, close, volume], ...]."""
