"""Anthropic Claude provider — claude-sonnet-4-20250514 by default."""

from __future__ import annotations

import logging
import os
import time

import httpx

from .base_provider import AIAdvice, AIProvider, parse_ai_response
from .prompt_builder import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)

ENDPOINT = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-4-20250514"
MIN_INTERVAL_S = 2.0


class ClaudeProvider(AIProvider):
    provider_id = "claude"
    display_name = "Claude (Anthropic)"

    def __init__(self) -> None:
        self._last_call = 0.0

    def _get_api_key(self) -> str:
        return os.environ.get("ANTHROPIC_API_KEY", "")

    def _get_model(self) -> str:
        return os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL)

    def is_configured(self) -> bool:
        return bool(self._get_api_key())

    async def consult(
        self,
        symbol: str,
        price: float,
        change_24h: float,
        indicators: dict,
        context: dict | None = None,
    ) -> AIAdvice | None:
        api_key = self._get_api_key()
        if not api_key:
            logger.warning("Anthropic API key not configured")
            return None

        # Rate limit
        elapsed = time.time() - self._last_call
        if elapsed < MIN_INTERVAL_S:
            import asyncio
            await asyncio.sleep(MIN_INTERVAL_S - elapsed)
        self._last_call = time.time()

        ctx = context or {}
        prompt = build_user_prompt(
            symbol=symbol,
            price=price,
            change_24h=change_24h,
            indicators=indicators,
            balance=ctx.get("balance"),
            open_trades=ctx.get("open_trades", 0),
            daily_pnl=ctx.get("daily_pnl", 0.0),
        )

        payload = {
            "model": self._get_model(),
            "max_tokens": 500,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.4,
        }

        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        ENDPOINT,
                        json=payload,
                        headers={
                            "x-api-key": api_key,
                            "anthropic-version": "2023-06-01",
                            "Content-Type": "application/json",
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()

                # Claude returns content as a list of blocks
                content_blocks = data.get("content", [])
                text = ""
                for block in content_blocks:
                    if block.get("type") == "text":
                        text += block.get("text", "")
                text = text.strip()

                if not text:
                    logger.warning("Claude returned empty response")
                    return None

                advice = parse_ai_response(text)
                if not advice:
                    if attempt == 0:
                        logger.warning("Claude unparseable response, retrying")
                        continue
                    return None

                advice.source = "Claude"
                logger.info(
                    "Claude %s: %s (%d%%) - %s",
                    symbol, advice.action, advice.confidence, advice.reasoning,
                )
                return advice

            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                if status in (401, 403):
                    logger.error("Claude auth error — check ANTHROPIC_API_KEY")
                    return None
                if status == 429:
                    logger.warning("Claude rate limited, backing off")
                    if attempt == 0:
                        import asyncio
                        await asyncio.sleep(5.0)
                        continue
                    return None
                logger.warning("Claude HTTP error (attempt %d): %s", attempt + 1, e)
                if attempt == 0:
                    import asyncio
                    await asyncio.sleep(2.0)
                    continue
                return None
            except Exception as e:
                logger.warning("Claude error (attempt %d): %s", attempt + 1, e)
                if attempt == 0:
                    import asyncio
                    await asyncio.sleep(2.0)
                    continue
                return None

        return None
