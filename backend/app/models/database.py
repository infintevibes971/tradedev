import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    """Create tables and run any missing column migrations."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Ensure passphrase_enc column exists (added after initial schema)
    async with engine.begin() as conn:
        try:
            await conn.execute(
                text("ALTER TABLE api_keys ADD COLUMN passphrase_enc BLOB")
            )
            logger.info("Migration: added passphrase_enc column to api_keys")
        except Exception:
            pass  # Column already exists — expected on fresh DBs


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
