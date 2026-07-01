from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import AppConfig
from app.core.loader import get_modules
from app.db.models import Base


def _set_sqlite_pragmas(dbapi_connection, connection_record) -> None:
    """Apply per-connection PRAGMAs on every new pooled SQLite connection.

    journal_mode=WAL is persisted in the database file itself, but synchronous
    and busy_timeout are *per-connection* settings that SQLite resets to their
    compiled-in defaults (synchronous=FULL) on every new connection. Setting
    them once in init_db() only affected that one bootstrap connection — every
    other connection the pool opened afterwards (i.e. basically all real
    traffic from the bot/userbot/jobs) silently ran with synchronous=FULL,
    forcing an fsync on every single commit. Under this app's write pattern
    (a commit per incoming message, per job tick, per account) that made
    writes dramatically slower and increased the odds of SQLITE_BUSY errors
    under concurrency — which in turn could cause a message row to not exist
    yet when its deletion event arrived a moment later, silently dropping the
    deletion alert. This listener guarantees every connection gets the same
    fast, safe settings, no matter how many connections the pool opens.
    """
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def create_engine(config: AppConfig):
    engine = create_async_engine(
        config.database_url,
        echo=False,
        pool_pre_ping=True,
    )
    if engine.dialect.name == "sqlite":
        event.listens_for(engine.sync_engine, "connect")(_set_sqlite_pragmas)
    return engine


async def _apply_light_migrations(conn) -> None:
    modules = get_modules()

    def migrate(sync_conn) -> None:
        for module in modules:
            if module.light_migrations is not None:
                module.light_migrations(sync_conn)

    await conn.run_sync(migrate)


async def init_db(config: AppConfig) -> async_sessionmaker[AsyncSession]:
    get_modules()
    engine = create_engine(config)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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
