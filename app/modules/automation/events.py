from __future__ import annotations

import logging
import time

from telethon import events

from app.core.module_api import TelethonContext
from app.modules.archive.service import MediaArchiveService, MessageService
from app.modules.settings.repository import AccountSettingsRepository
from app.telegram.client_utils import resolve_event_message

logger = logging.getLogger(__name__)

_away_last_reply: dict[tuple[int, int], float] = {}
AWAY_THROTTLE_SECONDS = 3600


async def _backup_own_message(
    *,
    client,
    session_factory,
    account_id: int,
    chat_id: int,
    message_id: int,
    media_dir,
) -> None:
    async with session_factory() as session:
        settings = await AccountSettingsRepository(session).get_or_create(account_id)
        if not settings.backup_own_messages:
            return
        archive_media = settings.archive_media

    message = await resolve_event_message(client, chat_id, message_id)
    if message is None:
        return

    media_type = None
    media_path = None
    if message.media:
        media_type, media_path = await MediaArchiveService.maybe_download(
            client=client,
            message=message,
            account_id=account_id,
            media_dir=media_dir,
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


def register_events(ctx: TelethonContext) -> None:
    client = ctx.client
    account_id = ctx.account_id
    session_factory = ctx.session_factory

    @client.on(events.NewMessage(outgoing=True, func=lambda e: e.is_private))
    async def on_private_outgoing(event: events.NewMessage.Event) -> None:
        try:
            await _backup_own_message(
                client=client,
                session_factory=session_factory,
                account_id=account_id,
                chat_id=event.chat_id,
                message_id=event.message.id,
                media_dir=ctx.config.media_dir,
            )
        except Exception:
            logger.debug("Own message backup failed", exc_info=True)

    @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
    async def on_private_incoming(event: events.NewMessage.Event) -> None:
        chat_id = event.chat_id
        try:
            async with session_factory() as session:
                settings = await AccountSettingsRepository(session).get_or_create(account_id)
                if not settings.away_mode_enabled or not settings.away_message:
                    return
                away_message = settings.away_message

            key = (account_id, chat_id)
            now = time.time()
            if now - _away_last_reply.get(key, 0) < AWAY_THROTTLE_SECONDS:
                return
            _away_last_reply[key] = now
            await client.send_message(chat_id, away_message)
        except Exception:
            logger.debug("Away mode reply failed", exc_info=True)
