from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import AppConfig
from app.db.models import Base


def create_engine(config: AppConfig):
    return create_async_engine(
        config.database_url,
        echo=False,
        pool_pre_ping=True,
    )


async def _apply_light_migrations(conn) -> None:
    def migrate(sync_conn) -> None:
        inspector = inspect(sync_conn)
        if "accounts" not in inspector.get_table_names():
            return
        columns = {col["name"] for col in inspector.get_columns("accounts")}
        if "username" not in columns:
            sync_conn.execute(text("ALTER TABLE accounts ADD COLUMN username VARCHAR(64)"))
        if "referral_code" not in columns:
            sync_conn.execute(text("ALTER TABLE accounts ADD COLUMN referral_code VARCHAR(16)"))
        if "referred_by" not in columns:
            sync_conn.execute(text("ALTER TABLE accounts ADD COLUMN referred_by VARCHAR(16)"))
        if "bot_chat_id" not in columns:
            sync_conn.execute(text("ALTER TABLE accounts ADD COLUMN bot_chat_id BIGINT"))
        if "stored_messages" in inspector.get_table_names():
            msg_columns = {col["name"] for col in inspector.get_columns("stored_messages")}
            indexes = {idx["name"] for idx in inspector.get_indexes("stored_messages")}
            if "deleted_at" not in msg_columns:
                sync_conn.execute(
                    text("ALTER TABLE stored_messages ADD COLUMN deleted_at DATETIME")
                )
            if "ix_stored_messages_deleted_at" not in indexes:
                sync_conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_stored_messages_deleted_at "
                        "ON stored_messages (deleted_at)"
                    )
                )

    await conn.run_sync(migrate)


async def init_db(config: AppConfig) -> async_sessionmaker[AsyncSession]:
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
