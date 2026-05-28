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
    redis_url: str = ""
    port: int = 8000

    max_concurrent_agents: int = 100
    default_paper_trading: bool = True

    model_config = {
        "env_file": str(_env_file),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
