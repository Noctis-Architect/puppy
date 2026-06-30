from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import AppConfig
from app.core.loader import discover_modules
from app.db.models import Base


def create_engine(config: AppConfig):
    return create_async_engine(
        config.database_url,
        echo=False,
        pool_pre_ping=True,
    )


async def _apply_light_migrations(conn) -> None:
    modules = discover_modules()

    def migrate(sync_conn) -> None:
        for module in modules:
            if module.light_migrations is not None:
                module.light_migrations(sync_conn)

    await conn.run_sync(migrate)


async def init_db(config: AppConfig) -> async_sessionmaker[AsyncSession]:
    discover_modules()
    engine = create_engine(config)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("PRAGMA journal_mode=WAL"))
        await conn.execute(text("PRAGMA busy_timeout=5000"))
        await conn.execute(text("PRAGMA synchronous=NORMAL"))
        await _apply_light_migrations(conn)
    return async_sessionmaker(engine, expire_on_commit=False)


async def session_scope(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
