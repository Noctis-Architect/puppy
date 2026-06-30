from __future__ import annotations

import logging
from datetime import datetime

from telethon import events

from app.core.module_api import TelethonContext
from app.modules.archive.notifier import DeletionService, NotifierService
from app.modules.archive.repository import MessageRepository
from app.modules.archive.service import MessageService
from app.telegram.client_utils import resolve_event_message

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

    async def _store_message(chat_id: int, message_id: int) -> None:
        try:
            message = await resolve_event_message(client, chat_id, message_id)
            if message is None:
                return

            sender = await message.get_sender()
            sender_id = sender.id if sender else message.chat_id

            async with session_factory() as session:
                from app.modules.settings.repository import TrackedTargetRepository

                target = await TrackedTargetRepository(session).get_target(
                    account_id=account_id,
                    target_user_id=sender_id,
                )
                if target is not None and not target.track_messages:
                    return

            media_type = None
            media_path = None
            if message.media:
                from app.modules.archive.service import MediaArchiveService
                from app.modules.settings.repository import AccountSettingsRepository

                async with session_factory() as session:
                    settings = await AccountSettingsRepository(session).get_or_create(
                        account_id
                    )
                    archive_media = settings.archive_media

                media_type, media_path = await MediaArchiveService.maybe_download(
                    client=client,
                    message=message,
                    account_id=account_id,
                    media_dir=ctx.config.media_dir,
                    archive_media=archive_media,
                )

            async with session_factory() as session:
                await MessageService(session).store_incoming(
                    account_id=account_id,
                    message=message,
                    media_type=media_type,
                    media_path=media_path,
                )
                await session.commit()
        except Exception:
            logger.exception(
                "Failed storing message account=%s chat=%s msg=%s",
                account_id,
                chat_id,
                message_id,
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
        await _store_message(event.chat_id, event.message.id)

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

    @client.on(events.MessageRead(inbox=True))
    async def on_message_read(event: events.MessageRead.Event) -> None:
        chat_id = event.chat_id
        if chat_id is None or chat_id < 0:
            return

        max_id = event.max_id
        if not max_id:
            return

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
