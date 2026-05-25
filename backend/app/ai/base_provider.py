"""Abstract base for all AI providers."""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AIAdvice:
    """Normalized response shape shared across all providers."""

    action: str = "HOLD"  # BUY | SELL | HOLD
    confidence: int = 0  # 0-100
    reasoning: str = ""
    risk_level: str = "MEDIUM"  # LOW | MEDIUM | HIGH
    suggested_stop_loss_pct: float | None = None
    suggested_take_profit_pct: float | None = None
    key_factors: list[str] = field(default_factory=list)
    source: str = ""
    available: bool = True

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "risk_level": self.risk_level,
            "suggested_stop_loss_pct": self.suggested_stop_loss_pct,
            "suggested_take_profit_pct": self.suggested_take_profit_pct,
            "key_factors": self.key_factors,
            "source": self.source,
            "available": self.available,
        }


def parse_ai_response(text: str) -> AIAdvice | None:
    """Parse structured JSON from any LLM response, with fallback extraction."""
    if not text:
        return None

    # Strip markdown fencing
    clean = text.strip()
    clean = re.sub(r"```json\n?", "", clean)
    clean = re.sub(r"```\n?", "", clean)
    clean = clean.strip()

    # Pull first {...} block
    match = re.search(r"\{[\s\S]*\}", clean)
    if match:
        clean = match.group(0)

    try:
        data = json.loads(clean)
    except json.JSONDecodeError:
        # Fallback: regex extraction
        return _extract_fallback(text)

    action = str(data.get("action", "HOLD")).upper()
    if action not in ("BUY", "SELL", "HOLD"):
        action = "HOLD"

    confidence = data.get("confidence", 50)
    if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 100:
        confidence = 50

    return AIAdvice(
        action=action,
        confidence=int(confidence),
        reasoning=str(data.get("reasoning", "")),
        risk_level=str(data.get("risk_level", "MEDIUM")),
        suggested_stop_loss_pct=data.get("suggested_stop_loss_pct"),
        suggested_take_profit_pct=data.get("suggested_take_profit_pct"),
        key_factors=data.get("key_factors", []),
    )


def _extract_fallback(text: str) -> AIAdvice | None:
    """Regex fallback for malformed JSON responses."""
    action_match = re.search(r'"action"\s*:\s*"(BUY|SELL|HOLD)"', text, re.IGNORECASE)
    if not action_match:
        return None

    conf_match = re.search(r'"confidence"\s*:\s*(\d+)', text)
    reason_match = re.search(r'"reasoning"\s*:\s*"([^"]+)"', text)

    return AIAdvice(
        action=action_match.group(1).upper(),
        confidence=int(conf_match.group(1)) if conf_match else 50,
        reasoning=reason_match.group(1) if reason_match else "Parsed from malformed response",
        risk_level="MEDIUM",
    )


class AIProvider(ABC):
    """Interface that all AI providers implement."""

    provider_id: str = ""
    display_name: str = ""

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if the provider has a valid API key."""

    @abstractmethod
    async def consult(
        self,
        symbol: str,
        price: float,
        change_24h: float,
        indicators: dict,
        context: dict | None = None,
    ) -> AIAdvice | None:
        """Ask the LLM for a trading opinion. Returns None on failure."""
