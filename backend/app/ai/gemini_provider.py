"""Google Gemini provider — gemini-2.0-flash by default."""

from __future__ import annotations

import logging
import os
import time
from urllib.parse import quote

import httpx

from .base_provider import AIAdvice, AIProvider, parse_ai_response
from .prompt_builder import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-2.0-flash"
MIN_INTERVAL_S = 2.0


def _endpoint(model: str) -> str:
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiProvider(AIProvider):
    provider_id = "gemini"
    display_name = "Google Gemini"

    def __init__(self) -> None:
        self._last_call = 0.0

    def _get_api_key(self) -> str:
        return os.environ.get("GEMINI_API_KEY", "")

    def _get_model(self) -> str:
        return os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)

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
            logger.warning("Gemini API key not configured")
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

        url = f"{_endpoint(self._get_model())}?key={quote(api_key)}"
        payload = {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.4,
                "maxOutputTokens": 500,
                "responseMimeType": "application/json",
            },
        }

        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(url, json=payload)
                    resp.raise_for_status()
                    data = resp.json()

                # Check safety filter blocks
                if data.get("promptFeedback", {}).get("blockReason"):
                    logger.warning(
                        "Gemini blocked prompt: %s",
                        data["promptFeedback"]["blockReason"],
                    )
                    return None

                candidate = (data.get("candidates") or [{}])[0]
                text = (
                    candidate.get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "")
                    .strip()
                )
                if not text:
                    logger.warning("Gemini returned empty response")
                    return None

                advice = parse_ai_response(text)
                if not advice:
                    if attempt == 0:
                        logger.warning("Gemini unparseable response, retrying")
                        continue
                    return None

                advice.source = "Gemini"
                logger.info(
                    "Gemini %s: %s (%d%%) - %s",
                    symbol, advice.action, advice.confidence, advice.reasoning,
                )
                return advice

            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                if status in (401, 403):
                    logger.error("Gemini auth error — check API key")
                    return None
                if status == 429:
                    logger.warning("Gemini rate limited, backing off")
                    if attempt == 0:
                        import asyncio
                        await asyncio.sleep(5.0)
                        continue
                    return None
                logger.warning("Gemini HTTP error (attempt %d): %s", attempt + 1, e)
                if attempt == 0:
                    import asyncio
                    await asyncio.sleep(2.0)
                    continue
                return None
            except Exception as e:
                logger.warning("Gemini error (attempt %d): %s", attempt + 1, e)
                if attempt == 0:
                    import asyncio
                    await asyncio.sleep(2.0)
                    continue
                return None

        return None
