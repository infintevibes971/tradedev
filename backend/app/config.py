import os
from pathlib import Path

from pydantic_settings import BaseSettings

# Look for .env in backend/ first, then project root
_backend_dir = Path(__file__).resolve().parent.parent
_project_root = _backend_dir.parent
_env_candidates = [_backend_dir / ".env", _project_root / ".env"]
_env_file = next((p for p in _env_candidates if p.is_file()), ".env")


class Settings(BaseSettings):
    app_name: str = "TradeDev"
    debug: bool = False
    log_level: str = "INFO"

    database_url: str = "sqlite+aiosqlite:///./tradedev.db"
    encryption_key: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""
    redis_url: str = ""
    port: int = 8000

    # AI config
    ai_mode: str = "single"
    ai_primary_provider: str = "gemini"
    ai_fallback_chain: str = ""

    max_concurrent_agents: int = 100
    default_paper_trading: bool = True

    model_config = {
        "env_file": str(_env_file),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()

# ── Propagate .env values into os.environ ──────────────────────
# The AI providers use os.environ.get() directly for hot-reloadable
# config. Pydantic_settings loads .env into its own object but does
# NOT set os.environ. We bridge the gap here at import time.
_ENV_KEYS = [
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "AI_MODE",
    "AI_PRIMARY_PROVIDER",
    "AI_FALLBACK_CHAIN",
    "ENCRYPTION_KEY",
]
for _key in _ENV_KEYS:
    _val = getattr(settings, _key.lower(), "")
    if _val and not os.environ.get(_key):
        os.environ[_key] = _val
