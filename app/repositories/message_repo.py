from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import StoredMessage


class MessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_incoming(
        self,
        *,
        account_id: int,
        chat_id: int,
        sender_id: int,
        message_id: int,
        text: str,
        sender_name: str | None,
        received_at: datetime | None = None,
        is_read: bool = False,
        read_at: datetime | None = None,
    ) -> StoredMessage:
        result = await self._session.execute(
            select(StoredMessage).where(
                StoredMessage.account_id == account_id,
                StoredMessage.chat_id == chat_id,
                StoredMessage.message_id == message_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.text = text
            existing.sender_name = sender_name
            if is_read and not existing.is_read:
                existing.is_read = True
                existing.read_at = read_at or datetime.now().astimezone()
            return existing

        message = StoredMessage(
            account_id=account_id,
            chat_id=chat_id,
            sender_id=sender_id,
            message_id=message_id,
            text=text,
            sender_name=sender_name,
            is_read=is_read,
            read_at=read_at if is_read else None,
            received_at=received_at or datetime.now().astimezone(),
        )
        self._session.add(message)
        await self._session.flush()
        return message

    async def get_by_message_ids(
        self,
        *,
        account_id: int,
        chat_id: int | None,
        message_ids: list[int],
    ) -> list[StoredMessage]:
        if not message_ids:
            return []
        conditions = [
            StoredMessage.account_id == account_id,
            StoredMessage.message_id.in_(message_ids),
        ]
        if chat_id is not None:
            conditions.append(StoredMessage.chat_id == chat_id)
        result = await self._session.execute(select(StoredMessage).where(*conditions))
        return list(result.scalars().all())

    async def mark_read_up_to(
        self,
        *,
        account_id: int,
        chat_id: int,
        max_message_id: int,
        read_at: datetime,
    ) -> int:
        result = await self._session.execute(
            update(StoredMessage)
            .where(
                StoredMessage.account_id == account_id,
                StoredMessage.chat_id == chat_id,
                StoredMessage.message_id <= max_message_id,
                StoredMessage.is_read.is_(False),
            )
            .values(is_read=True, read_at=read_at)
        )
        return result.rowcount or 0

    async def mark_deleted(
        self,
        *,
        account_id: int,
        chat_id: int | None,
        message_ids: list[int],
        deleted_at: datetime,
    ) -> list[StoredMessage]:
        messages = await self.get_by_message_ids(
            account_id=account_id,
            chat_id=chat_id,
            message_ids=message_ids,
        )
        if not messages:
            return []
        for message in messages:
            message.deleted_at = deleted_at
        await self._session.flush()
        return messages

    async def count_deleted_since(
        self,
        *,
        account_id: int,
        since: datetime,
    ) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(StoredMessage)
            .where(
                StoredMessage.account_id == account_id,
                StoredMessage.deleted_at.is_not(None),
                StoredMessage.deleted_at >= since,
            )
        )
        return int(result.scalar_one())

    async def list_deleted_since(
        self,
        *,
        account_id: int,
        since: datetime,
        offset: int = 0,
        limit: int = 10,
    ) -> list[StoredMessage]:
        result = await self._session.execute(
            select(StoredMessage)
            .where(
                StoredMessage.account_id == account_id,
                StoredMessage.deleted_at.is_not(None),
                StoredMessage.deleted_at >= since,
            )
            .order_by(StoredMessage.deleted_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def delete_read_between(
        self,
        *,
        start: datetime,
        end: datetime,
    ) -> int:
        result = await self._session.execute(
            delete(StoredMessage).where(
                and_(
                    StoredMessage.is_read.is_(True),
                    StoredMessage.read_at.is_not(None),
                    StoredMessage.read_at >= start,
                    StoredMessage.read_at < end,
                    StoredMessage.deleted_at.is_(None),
                )
            )
        )
        return result.rowcount or 0

    async def delete_expired_deleted(self, *, before: datetime) -> int:
        result = await self._session.execute(
            delete(StoredMessage).where(
                and_(
                    StoredMessage.deleted_at.is_not(None),
                    StoredMessage.deleted_at < before,
                )
            )
        )
        return result.rowcount or 0

    async def get_account_stats(self, account_id: int) -> dict[str, int | datetime | None]:
        total = await self._session.scalar(
            select(func.count())
            .select_from(StoredMessage)
            .where(StoredMessage.account_id == account_id)
        ) or 0
        deleted = await self._session.scalar(
            select(func.count())
            .select_from(StoredMessage)
            .where(
                StoredMessage.account_id == account_id,
                StoredMessage.deleted_at.is_not(None),
            )
        ) or 0
        last_received = await self._session.scalar(
            select(func.max(StoredMessage.received_at)).where(
                StoredMessage.account_id == account_id
            )
        )
        last_deleted = await self._session.scalar(
            select(func.max(StoredMessage.deleted_at)).where(
                StoredMessage.account_id == account_id,
                StoredMessage.deleted_at.is_not(None),
            )
        )
        return {
            "total": int(total),
            "deleted": int(deleted),
            "last_received": last_received,
            "last_deleted": last_deleted,
        }

    async def list_recent_activity(self, *, limit: int = 15) -> list[StoredMessage]:
        result = await self._session.execute(
            select(StoredMessage)
            .where(StoredMessage.deleted_at.is_not(None))
            .order_by(StoredMessage.deleted_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
