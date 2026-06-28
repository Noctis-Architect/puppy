from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.message_repo import MessageRepository
from app.telegram.utils import extract_message_text, format_sender_name
from telethon.tl.custom.message import Message


class MessageService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = MessageRepository(session)

    async def store_incoming(
        self,
        *,
        account_id: int,
        message: Message,
        is_read: bool = False,
        read_at: datetime | None = None,
    ) -> None:
        sender = await message.get_sender()
        sender_id = sender.id if sender else message.chat_id
        await self._repo.upsert_incoming(
            account_id=account_id,
            chat_id=message.chat_id,
            sender_id=sender_id,
            message_id=message.id,
            text=extract_message_text(message),
            sender_name=format_sender_name(message),
            received_at=message.date.replace(tzinfo=message.date.tzinfo)
            if message.date
            else datetime.now().astimezone(),
            is_read=is_read,
            read_at=read_at,
        )

    async def store_message(
        self,
        *,
        account_id: int,
        message: Message,
        is_read: bool,
    ) -> None:
        read_at = datetime.now().astimezone() if is_read else None
        await self.store_incoming(
            account_id=account_id,
            message=message,
            is_read=is_read,
            read_at=read_at,
        )


async def with_message_service(
    factory: async_sessionmaker[AsyncSession],
    callback,
):
    async with factory() as session:
        service = MessageService(session)
        result = await callback(service)
        await session.commit()
        return result
