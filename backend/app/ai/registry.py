"""AI Provider Registry — orchestrates multi-LLM trading advice.

Ported from trading-agent-1's aiProviders/index.js architecture.

Modes:
  - single:    Use primary provider; on failure, walk fallback chain.
  - consensus: Call two providers in parallel; require agreement.
  - disabled:  Return HOLD with no AI calls.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass

from .base_provider import AIAdvice, AIProvider
from .claude_provider import ClaudeProvider
from .gemini_provider import GeminiProvider
from .openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)

# Provider instances — singletons
_openai = OpenAIProvider()
_gemini = GeminiProvider()
_claude = ClaudeProvider()

PROVIDERS: dict[str, AIProvider] = {
    "openai": _openai,
    "gemini": _gemini,
    "claude": _claude,
}

VALID_MODES = ("single", "consensus", "disabled")
DEFAULT_MODE = "single"
DEFAULT_PRIMARY = "claude"

RISK_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}


# ─── Config readers (env-backed, hot-reloadable) ────────────────────────────


def get_mode() -> str:
    mode = os.environ.get("AI_MODE", DEFAULT_MODE).lower()
    return mode if mode in VALID_MODES else DEFAULT_MODE


def get_primary() -> str:
    primary = os.environ.get("AI_PRIMARY_PROVIDER", DEFAULT_PRIMARY).lower()
    return primary if primary in PROVIDERS else DEFAULT_PRIMARY


def get_fallback_chain() -> list[str]:
    raw = os.environ.get("AI_FALLBACK_CHAIN", "")
    return [p.strip().lower() for p in raw.split(",") if p.strip().lower() in PROVIDERS]


@dataclass
class RegistryStatus:
    mode: str
    primary: str
    fallback_chain: list[str]
    providers: dict[str, dict]


def get_status() -> RegistryStatus:
    return RegistryStatus(
        mode=get_mode(),
        primary=get_primary(),
        fallback_chain=get_fallback_chain(),
        providers={
            pid: {
                "id": pid,
                "display_name": p.display_name,
                "configured": p.is_configured(),
            }
            for pid, p in PROVIDERS.items()
        },
    )


# ─── Consensus logic ────────────────────────────────────────────────────────


def _highest_risk(a: str, b: str) -> str:
    return a if RISK_ORDER.get(a, 1) >= RISK_ORDER.get(b, 1) else b


def _avg_if_both(a: float | None, b: float | None) -> float | None:
    if a is None and b is None:
        return None
    if a is None:
        return b
    if b is None:
        return a
    return round((a + b) / 2, 1)


def _combine_consensus(a: AIAdvice | None, b: AIAdvice | None) -> AIAdvice | None:
    if not a and not b:
        return None
    if not a:
        b.source = f"{b.source} (consensus, other down)"
        return b
    if not b:
        a.source = f"{a.source} (consensus, other down)"
        return a

    # Both succeeded — strict agreement
    if a.action != b.action:
        return AIAdvice(
            action="HOLD",
            confidence=0,
            reasoning=(
                f"AI disagreement: {a.source}={a.action}@{a.confidence}%, "
                f"{b.source}={b.action}@{b.confidence}%"
            ),
            risk_level=_highest_risk(a.risk_level, b.risk_level),
            source="Consensus (disagreement)",
        )

    # Both agree — average confidence
    avg_conf = round((a.confidence + b.confidence) / 2)
    return AIAdvice(
        action=a.action,
        confidence=avg_conf,
        reasoning=(
            f"[Consensus] {a.source}({a.confidence}%): {a.reasoning} | "
            f"{b.source}({b.confidence}%): {b.reasoning}"
        ),
        risk_level=_highest_risk(a.risk_level, b.risk_level),
        suggested_stop_loss_pct=_avg_if_both(
            a.suggested_stop_loss_pct, b.suggested_stop_loss_pct
        ),
        suggested_take_profit_pct=_avg_if_both(
            a.suggested_take_profit_pct, b.suggested_take_profit_pct
        ),
        key_factors=(a.key_factors + b.key_factors)[:5],
        source="Consensus (agreed)",
    )


# ─── Public API ──────────────────────────────────────────────────────────────


async def consult(
    symbol: str,
    price: float,
    change_24h: float,
    indicators: dict,
    context: dict | None = None,
) -> AIAdvice:
    """Ask the configured AI provider(s) for a trading opinion.

    Returns an AIAdvice object — never None. On total failure returns HOLD.
    """
    mode = get_mode()

    if mode == "disabled":
        return AIAdvice(
            action="HOLD",
            confidence=0,
            reasoning="AI disabled — running on technicals only",
            source="disabled",
            available=False,
        )

    if mode == "single":
        return await _consult_single(symbol, price, change_24h, indicators, context)

    # mode == "consensus"
    return await _consult_consensus(symbol, price, change_24h, indicators, context)


async def _consult_single(
    symbol: str,
    price: float,
    change_24h: float,
    indicators: dict,
    context: dict | None,
) -> AIAdvice:
    primary = get_primary()
    fallbacks = [p for p in get_fallback_chain() if p != primary]
    chain = [primary, *fallbacks]
    tried: list[str] = []

    for i, pid in enumerate(chain):
        provider = PROVIDERS.get(pid)
        if not provider:
            continue
        if not provider.is_configured():
            tried.append(f"{pid}(not-configured)")
            continue

        result = await provider.consult(symbol, price, change_24h, indicators, context)
        if result:
            if i > 0:
                logger.info(
                    "Fallback via %s for %s (tried: %s)",
                    pid, symbol, ", ".join(tried),
                )
            return result

        tried.append(f"{pid}(null)")
        logger.info("%s returned no result for %s, trying next", pid, symbol)

    logger.warning("All providers exhausted for %s (tried: %s)", symbol, ", ".join(tried))
    return _hold_fallback(f"All providers unavailable ({', '.join(tried) or 'none configured'})")


async def _consult_consensus(
    symbol: str,
    price: float,
    change_24h: float,
    indicators: dict,
    context: dict | None,
) -> AIAdvice:
    """Call two providers in parallel; require agreement."""
    primary = get_primary()

    # Pick two configured providers for consensus
    consensus_ids = [pid for pid in PROVIDERS if PROVIDERS[pid].is_configured()]
    if len(consensus_ids) < 2:
        if consensus_ids:
            # Only one available — use it alone
            provider = PROVIDERS[consensus_ids[0]]
            result = await provider.consult(
                symbol, price, change_24h, indicators, context
            )
            if result:
                result.source = f"{result.source} (consensus, only provider)"
                return result
        return _hold_fallback("Less than 2 providers available for consensus")

    # Take first two configured providers
    p1, p2 = PROVIDERS[consensus_ids[0]], PROVIDERS[consensus_ids[1]]
    r1, r2 = await asyncio.gather(
        p1.consult(symbol, price, change_24h, indicators, context),
        p2.consult(symbol, price, change_24h, indicators, context),
    )

    combined = _combine_consensus(r1, r2)
    if not combined:
        return _hold_fallback("Both providers failed in consensus mode")

    logger.info(
        "%s consensus: %s (%d%%) [%s]",
        symbol, combined.action, combined.confidence, combined.source,
    )
    return combined


def _hold_fallback(reason: str) -> AIAdvice:
    return AIAdvice(
        action="HOLD",
        confidence=0,
        reasoning=reason,
        source="fallback",
        available=False,
    )


def is_available() -> bool:
    """Return True if at least one provider is configured and mode != disabled."""
    if get_mode() == "disabled":
        return False
    return any(p.is_configured() for p in PROVIDERS.values())
