from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from telethon import events

from app.core.module_api import TelethonContext
from app.modules.archive.notifier import DeletionService, NotifierService
from app.modules.archive.repository import MessageRepository
from app.modules.archive.service import persist_incoming_message

logger = logging.getLogger(__name__)


def _is_private_incoming(event: events.NewMessage.Event) -> bool:
    return bool(
        event.is_private and not event.out and not event.is_group and not event.is_channel
    )


async def _is_monitored_group(session_factory, account_id: int, chat_id: int) -> bool:
    try:
        from app.modules.settings.repository import MonitoredChatRepository

        async with session_factory() as session:
            repo = MonitoredChatRepository(session)
            return await repo.is_monitored(account_id=account_id, chat_id=chat_id)
    except Exception:
        return False


def register_events(ctx: TelethonContext) -> None:
    client = ctx.client
    account_id = ctx.account_id
    session_factory = ctx.session_factory

    async def _store_message(message) -> None:
        try:
            await persist_incoming_message(
                client=client,
                session_factory=session_factory,
                account_id=account_id,
                message=message,
                media_dir=ctx.config.media_dir,
            )
        except Exception:
            logger.exception(
                "Failed storing message account=%s chat=%s msg=%s",
                account_id,
                getattr(message, "chat_id", None),
                getattr(message, "id", None),
            )

    async def _notify_deleted(peer_id: int, messages: list) -> None:
        try:
            await NotifierService.notify_deleted_messages(
                bot=ctx.bot,
                bot_chat_id=ctx.bot_chat_id,
                owner_telegram_id=ctx.owner_telegram_id,
                client=client,
                messages=messages,
            )
        except Exception:
            logger.exception(
                "Failed notifying deletion account=%s chat=%s",
                account_id,
                peer_id,
            )

    @client.on(events.NewMessage(func=_is_private_incoming))
    async def on_incoming_message(event: events.NewMessage.Event) -> None:
        asyncio.create_task(_store_message(event.message))

    @client.on(events.MessageDeleted())
    async def on_message_deleted(event: events.MessageDeleted.Event) -> None:
        chat_id = event.chat_id
        deleted_ids = list(event.deleted_ids)
        if not deleted_ids:
            return

        # Private chats and small groups: Telegram sends no peer on delete (chat_id is None).
        # We match stored rows by message_id alone — see Telethon MessageDeleted docs.
        if chat_id is not None and chat_id < 0:
            if not await _is_monitored_group(session_factory, account_id, chat_id):
                return

        lookup_chat_id = chat_id

        async def _handle() -> None:
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
                    await _notify_deleted(peer_id, messages)
            except Exception:
                logger.exception(
                    "Failed handling deletion account=%s chat=%s ids=%s",
                    account_id,
                    chat_id,
                    deleted_ids,
                )

        asyncio.create_task(_handle())

    @client.on(events.MessageRead(inbox=True))
    async def on_message_read(event: events.MessageRead.Event) -> None:
        chat_id = event.chat_id
        if chat_id is None or chat_id < 0:
            return

        max_id = event.max_id
        if not max_id:
            return

        async def _handle() -> None:
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

        asyncio.create_task(_handle())
