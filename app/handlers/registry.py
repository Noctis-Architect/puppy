from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from telethon import TelegramClient, events

from app.repositories.message_repo import MessageRepository
from app.services.deletion_service import DeletionService, NotifierService
from app.services.message_service import MessageService

logger = logging.getLogger(__name__)


def _is_private_incoming(event: events.NewMessage.Event) -> bool:
    return bool(
        event.is_private and not event.out and not event.is_group and not event.is_channel
    )


def register_handlers(
    *,
    client: TelegramClient,
    account_id: int,
    owner_telegram_id: int,
    session_factory: async_sessionmaker[AsyncSession],
    bot: Bot | None = None,
    bot_chat_id: int | None = None,
) -> None:
    async def _store_message(event: events.NewMessage.Event) -> None:
        try:
            async with session_factory() as session:
                await MessageService(session).store_incoming(
                    account_id=account_id,
                    message=event.message,
                )
                await session.commit()
            logger.debug(
                "Stored message account=%s chat=%s msg=%s",
                account_id,
                event.chat_id,
                event.message.id,
            )
        except Exception:
            logger.exception(
                "Failed storing message account=%s chat=%s msg=%s",
                account_id,
                event.chat_id,
                event.message.id,
            )

    async def _notify_deleted(peer_id: int, messages: list) -> None:
        try:
            await NotifierService.notify_deleted_messages(
                bot=bot,
                bot_chat_id=bot_chat_id,
                owner_telegram_id=owner_telegram_id,
                client=client,
                messages=messages,
            )
            logger.info(
                "Notified deletion account=%s chat=%s count=%s",
                account_id,
                peer_id,
                len(messages),
            )
        except Exception:
            logger.exception(
                "Failed notifying deletion account=%s chat=%s",
                account_id,
                peer_id,
            )

    @client.on(events.NewMessage(func=_is_private_incoming))
    async def on_incoming_message(event: events.NewMessage.Event) -> None:
        asyncio.create_task(_store_message(event))

    @client.on(events.MessageDeleted())
    async def on_message_deleted(event: events.MessageDeleted.Event) -> None:
        chat_id = event.chat_id
        if chat_id is not None and chat_id < 0:
            return

        deleted_ids = list(event.deleted_ids)
        if not deleted_ids:
            return

        # Telegram omits chat_id for private/small-group deletions; look up by message_id.
        lookup_chat_id = chat_id if chat_id is not None else None

        try:
            async with session_factory() as session:
                deletion = DeletionService(session)
                deleted_messages = await deletion.handle_deleted(
                    account_id=account_id,
                    chat_id=lookup_chat_id,
                    message_ids=deleted_ids,
                )
                await session.commit()

            by_chat: dict[int, list] = {}
            for msg in deleted_messages:
                by_chat.setdefault(msg.chat_id, []).append(msg)

            for peer_id, messages in by_chat.items():
                asyncio.create_task(_notify_deleted(peer_id, messages))
        except Exception:
            logger.exception(
                "Failed handling deletion account=%s chat=%s ids=%s",
                account_id,
                chat_id,
                deleted_ids,
            )

    @client.on(events.MessageRead(inbox=True))
    async def on_message_read(event: events.MessageRead.Event) -> None:
        chat_id = event.chat_id
        if chat_id is None or chat_id < 0:
            return

        max_id = event.max_id
        if not max_id:
            return

        async def _mark_read() -> None:
            try:
                async with session_factory() as session:
                    repo = MessageRepository(session)
                    updated = await repo.mark_read_up_to(
                        account_id=account_id,
                        chat_id=chat_id,
                        max_message_id=max_id,
                        read_at=datetime.now().astimezone(),
                    )
                    await session.commit()
                if updated:
                    logger.debug(
                        "Marked %s message(s) read account=%s chat=%s",
                        updated,
                        account_id,
                        chat_id,
                    )
            except Exception:
                logger.exception(
                    "Failed marking read account=%s chat=%s max_id=%s",
                    account_id,
                    chat_id,
                    max_id,
                )

        asyncio.create_task(_mark_read())
