from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Account, Base
from app.modules.archive.models import StoredMessage  # noqa: F401 — register table
from app.modules.archive.repository import MessageRepository


async def _make_repo(tmp_path) -> MessageRepository:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        session.add(
            Account(
                id=1,
                telegram_id=111,
                phone="+10000000000",
                username="owner",
                session_path="/tmp/session",
                is_active=True,
            )
        )
        session.add(
            StoredMessage(
                account_id=1,
                chat_id=222,
                sender_id=333,
                message_id=99,
                text="hello",
            )
        )
        await session.commit()
        return MessageRepository(session), factory


@pytest.mark.asyncio
async def test_mark_deleted_without_chat_id_finds_private_message(tmp_path) -> None:
    repo, factory = await _make_repo(tmp_path)
    deleted_at = datetime.now(timezone.utc)
    found = await repo.mark_deleted(
        account_id=1,
        chat_id=None,
        message_ids=[99],
        deleted_at=deleted_at,
    )
    async with factory() as session:
        await session.commit()

    assert len(found) == 1
    assert found[0].message_id == 99
    assert found[0].deleted_at == deleted_at


@pytest.mark.asyncio
async def test_mark_deleted_with_wrong_chat_id_does_not_match(tmp_path) -> None:
    repo, _factory = await _make_repo(tmp_path)
    deleted_at = datetime.now(timezone.utc)
    found = await repo.mark_deleted(
        account_id=1,
        chat_id=999,
        message_ids=[99],
        deleted_at=deleted_at,
    )

    assert found == []
