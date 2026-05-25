"""OpenAI ChatGPT provider — gpt-4o-mini by default."""

from __future__ import annotations

import logging
import os
import time

import httpx

from .base_provider import AIAdvice, AIProvider, parse_ai_response
from .prompt_builder import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)

ENDPOINT = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-4o-mini"
MIN_INTERVAL_S = 2.0


class OpenAIProvider(AIProvider):
    provider_id = "openai"
    display_name = "ChatGPT (OpenAI)"

    def __init__(self) -> None:
        self._last_call = 0.0

    def _get_api_key(self) -> str:
        return os.environ.get("OPENAI_API_KEY", "")

    def _get_model(self) -> str:
        return os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)

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
            logger.warning("OpenAI API key not configured")
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
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.4,
            "max_tokens": 500,
        }

        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        ENDPOINT,
                        json=payload,
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()

                text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                if not text:
                    logger.warning("OpenAI returned empty response")
                    return None

                advice = parse_ai_response(text)
                if not advice:
                    if attempt == 0:
                        logger.warning("OpenAI unparseable response, retrying")
                        continue
                    return None

                advice.source = "OpenAI"
                logger.info(
                    "OpenAI %s: %s (%d%%) - %s",
                    symbol, advice.action, advice.confidence, advice.reasoning,
                )
                return advice

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    logger.error("OpenAI auth error — check API key")
                    return None
                if e.response.status_code == 429:
                    logger.warning("OpenAI rate limited, backing off")
                    if attempt == 0:
                        import asyncio
                        await asyncio.sleep(5.0)
                        continue
                    return None
                logger.warning("OpenAI HTTP error (attempt %d): %s", attempt + 1, e)
                if attempt == 0:
                    import asyncio
                    await asyncio.sleep(2.0)
                    continue
                return None
            except Exception as e:
                logger.warning("OpenAI error (attempt %d): %s", attempt + 1, e)
                if attempt == 0:
                    import asyncio
                    await asyncio.sleep(2.0)
                    continue
                return None

        return None
