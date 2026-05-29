"""Exchange Manager — connects stored API keys to live exchange adapters.

This is the missing link between the KeyVault (encrypted storage) and the
LiveAdapter (real exchange connection). It reads stored keys from the DB,
decrypts them, creates LiveAdapter instances, and provides a unified
interface to query balances across all connected exchanges.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exchange.adapter import ExchangeAdapter
from app.exchange.live import LiveAdapter
from app.exchange.mock import MockAdapter
from app.models.database import async_session
from app.models.user import ApiKey
from app.security.vault import vault

logger = logging.getLogger(__name__)


class ExchangeManager:
    """Manages multiple exchange connections — mock + any number of live.

    Reads encrypted API keys from the DB, creates LiveAdapters, and
    aggregates balances across all connected exchanges.
    """

    def __init__(self) -> None:
        self._mock = MockAdapter()
        self._live_adapters: dict[str, LiveAdapter] = {}  # keyed by api_key DB id
        self._active_exchange: ExchangeAdapter = self._mock
        self._active_exchange_name: str = "paper"
        self._registry = None  # set by main.py after registry creation

    def set_registry(self, registry) -> None:
        """Store a reference to the agent registry for live-switching bots."""
        self._registry = registry

    @property
    def active(self) -> ExchangeAdapter:
        """The currently active exchange adapter (used by bots and portfolio)."""
        return self._active_exchange

    @property
    def active_name(self) -> str:
        return self._active_exchange_name

    @property
    def is_live(self) -> bool:
        return self._active_exchange is not self._mock

    async def load_user_keys(self, user_id: str) -> list[dict]:
        """Load all API keys for a user from the DB and create live adapters.

        Returns list of connected exchange info dicts.
        """
        connected = []

        async with async_session() as session:
            result = await session.execute(
                select(ApiKey).where(ApiKey.user_id == user_id)
            )
            keys = result.scalars().all()

        for key in keys:
            try:
                api_key = vault.decrypt(key.api_key_enc)
                api_secret = vault.decrypt(key.api_secret_enc)
                passphrase = None
                if key.passphrase_enc:
                    passphrase = vault.decrypt(key.passphrase_enc)

                adapter = LiveAdapter(
                    exchange_id=key.exchange,
                    api_key=api_key,
                    api_secret=api_secret,
                    passphrase=passphrase,
                    sandbox=key.is_paper,
                )
                self._live_adapters[key.id] = adapter
                connected.append({
                    "id": key.id,
                    "exchange": key.exchange,
                    "is_paper": key.is_paper,
                    "status": "connected",
                })
                logger.info(
                    "Connected to %s (%s)",
                    key.exchange,
                    "paper" if key.is_paper else "live",
                )
            except Exception as e:
                connected.append({
                    "id": key.id,
                    "exchange": key.exchange,
                    "is_paper": key.is_paper,
                    "status": "error",
                    "error": str(e),
                })
                logger.warning("Failed to connect %s: %s", key.exchange, e)

        return connected

    async def connect_key(self, key_id: str) -> dict:
        """Connect a single stored API key by its DB id."""
        async with async_session() as session:
            key = await session.get(ApiKey, key_id)
            if not key:
                return {"status": "error", "error": "Key not found"}

        try:
            api_key = vault.decrypt(key.api_key_enc)
            api_secret = vault.decrypt(key.api_secret_enc)
            passphrase = None
            if key.passphrase_enc:
                passphrase = vault.decrypt(key.passphrase_enc)

            adapter = LiveAdapter(
                exchange_id=key.exchange,
                api_key=api_key,
                api_secret=api_secret,
                passphrase=passphrase,
                sandbox=key.is_paper,
            )
            self._live_adapters[key.id] = adapter
            logger.info("Connected to %s", key.exchange)
            return {"status": "connected", "exchange": key.exchange}
        except Exception as e:
            logger.warning("Failed to connect %s: %s", key.exchange, e)
            return {"status": "error", "error": str(e)}

    async def switch_to_live(self, key_id: str) -> bool:
        """Switch the active exchange to a connected live adapter.

        Also hot-swaps all running trader bots to use the live adapter
        so they trade on the real exchange immediately.
        """
        adapter = self._live_adapters.get(key_id)
        if not adapter:
            return False
        self._active_exchange = adapter
        self._active_exchange_name = adapter.exchange_id
        self._update_bot_exchanges(adapter)
        logger.info("Switched active exchange to %s", adapter.exchange_id)
        return True

    def switch_to_paper(self) -> None:
        """Switch back to paper trading (MockAdapter)."""
        self._active_exchange = self._mock
        self._active_exchange_name = "paper"
        self._update_bot_exchanges(self._mock)
        logger.info("Switched to paper trading")

    def _update_bot_exchanges(self, adapter: ExchangeAdapter) -> None:
        """Hot-swap all running trader bots to a new exchange adapter.

        This is the critical link: when a user connects OKX (or switches
        back to paper), every running bot's `self.exchange` gets updated
        so trades flow through the correct adapter immediately.
        """
        if not self._registry:
            return
        agents = self._registry.list_agents()
        count = 0
        for info in agents:
            if not info.get("role", "").startswith("trader:"):
                continue
            agent = self._registry.get(info["agent_id"])
            if agent and hasattr(agent, "exchange"):
                agent.exchange = adapter
                count += 1
        if count:
            logger.info(
                "Hot-swapped %d trading bot(s) to %s",
                count, adapter.exchange_id,
            )

    async def get_all_balances(self) -> dict[str, dict]:
        """Get balances from all connected exchanges + mock.

        Returns {exchange_name: {asset: balance, ...}, ...}
        """
        all_balances: dict[str, dict] = {}

        # Mock balance
        try:
            mock_bal = await self._mock.get_balance()
            all_balances["paper"] = {k: str(v) for k, v in mock_bal.items()}
        except Exception as e:
            logger.warning("Failed to get mock balance: %s", e)

        # Live balances
        for key_id, adapter in self._live_adapters.items():
            try:
                bal = await adapter.get_balance()
                name = adapter.exchange_id
                all_balances[name] = {k: str(v) for k, v in bal.items()}
            except Exception as e:
                logger.warning(
                    "Failed to get balance from %s: %s",
                    adapter.exchange_id, e,
                )
                all_balances[adapter.exchange_id] = {"error": str(e)}

        return all_balances

    async def get_active_balance(self) -> dict[str, Decimal]:
        """Get balance from the currently active exchange."""
        return await self._active_exchange.get_balance()

    def get_status(self) -> dict:
        """Return current connection status."""
        return {
            "active_exchange": self._active_exchange_name,
            "is_live": self.is_live,
            "connected_exchanges": [
                {
                    "key_id": kid,
                    "exchange": adapter.exchange_id,
                }
                for kid, adapter in self._live_adapters.items()
            ],
            "paper_available": True,
        }

    async def close_all(self) -> None:
        """Close all live adapter connections."""
        for adapter in self._live_adapters.values():
            try:
                await adapter.close()
            except Exception:
                pass
        self._live_adapters.clear()
        self._active_exchange = self._mock
        self._active_exchange_name = "paper"
