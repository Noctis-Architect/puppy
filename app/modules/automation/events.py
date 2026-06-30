from __future__ import annotations

import asyncio
import logging
import time

from telethon import events

from app.core.module_api import TelethonContext
from app.modules.archive.service import MessageService
from app.modules.settings.repository import AccountSettingsRepository

logger = logging.getLogger(__name__)

_away_last_reply: dict[tuple[int, int], float] = {}
AWAY_THROTTLE_SECONDS = 3600


def register_events(ctx: TelethonContext) -> None:
    client = ctx.client
    account_id = ctx.account_id
    session_factory = ctx.session_factory

    @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
    async def on_private_incoming(event: events.NewMessage.Event) -> None:
        if event.out:
            try:
                async with session_factory() as session:
                    settings = await AccountSettingsRepository(session).get_or_create(account_id)
                    if settings.backup_own_messages:
                        await MessageService(session).store_incoming(
                            account_id=account_id,
                            message=event.message,
                        )
                        await session.commit()
            except Exception:
                logger.debug("Own message backup failed", exc_info=True)
            return

        try:
            async with session_factory() as session:
                settings = await AccountSettingsRepository(session).get_or_create(account_id)
                if not settings.away_mode_enabled or not settings.away_message:
                    return
                away_message = settings.away_message

            key = (account_id, event.chat_id)
            now = time.time()
            if now - _away_last_reply.get(key, 0) < AWAY_THROTTLE_SECONDS:
                return
            _away_last_reply[key] = now
            await client.send_message(event.chat_id, away_message)
        except Exception:
            logger.debug("Away mode reply failed", exc_info=True)
