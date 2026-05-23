from pathlib import Path

from pydantic_settings import BaseSettings


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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
