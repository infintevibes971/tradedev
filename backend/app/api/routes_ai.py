"""API routes for AI provider management."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.ai.registry import (
    PROVIDERS,
    VALID_MODES,
    get_mode,
    get_primary,
    get_status,
    is_available,
)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/status")
async def ai_status() -> dict:
    """Current state of the AI provider registry."""
    status = get_status()
    return {
        "available": is_available(),
        "mode": status.mode,
        "primary": status.primary,
        "fallback_chain": status.fallback_chain,
        "valid_modes": list(VALID_MODES),
        "providers": status.providers,
    }


@router.get("/providers")
async def list_providers() -> list[dict]:
    """List all available AI providers and their configuration status."""
    return [
        {
            "id": pid,
            "display_name": p.display_name,
            "configured": p.is_configured(),
        }
        for pid, p in PROVIDERS.items()
    ]


class ModeUpdate(BaseModel):
    mode: str


@router.post("/mode")
async def set_mode(body: ModeUpdate) -> dict:
    """Switch AI mode at runtime.

    Updates the AI_MODE env var (hot-reloadable — takes effect immediately
    on the next consult() call). Valid modes: single, consensus, disabled.
    """
    import os

    mode = body.mode.lower()
    if mode not in VALID_MODES:
        raise HTTPException(400, f"Invalid mode '{mode}'. Valid: {', '.join(VALID_MODES)}")

    os.environ["AI_MODE"] = mode
    return {"mode": get_mode(), "message": f"AI mode switched to '{mode}'"}


class PrimaryUpdate(BaseModel):
    provider: str


@router.post("/primary")
async def set_primary(body: PrimaryUpdate) -> dict:
    """Switch primary AI provider at runtime."""
    import os

    provider = body.provider.lower()
    if provider not in PROVIDERS:
        raise HTTPException(400, f"Unknown provider '{provider}'. Available: {', '.join(PROVIDERS)}")

    if not PROVIDERS[provider].is_configured():
        raise HTTPException(
            400,
            f"Provider '{provider}' is not configured — set its API key first",
        )

    os.environ["AI_PRIMARY_PROVIDER"] = provider
    return {"primary": get_primary(), "message": f"Primary provider set to '{provider}'"}
