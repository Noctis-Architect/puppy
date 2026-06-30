from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from telethon import events

from app.core.module_api import TelethonContext
from app.modules.archive.notifier import NotifierService
from app.modules.archive.repository import MessageRepository
from app.telegram.utils import extract_message_text

logger = logging.getLogger(__name__)


def register_events(ctx: TelethonContext) -> None:
    client = ctx.client
    account_id = ctx.account_id
    session_factory = ctx.session_factory

    @client.on(events.MessageEdited())
    async def on_message_edited(event: events.MessageEdited.Event) -> None:
        chat_id = event.chat_id
        if chat_id is None:
            return

        try:
            from app.modules.settings.repository import AccountSettingsRepository

            async with session_factory() as session:
                settings = await AccountSettingsRepository(session).get_or_create(account_id)
                if not settings.track_edits:
                    return

            new_text = extract_message_text(event.message)
            async with session_factory() as session:
                repo = MessageRepository(session)
                existing = await repo.get_by_id(
                    account_id=account_id,
                    chat_id=chat_id,
                    message_id=event.message.id,
                )
                if not existing:
                    return
                old_text = existing.text
                updated = await repo.record_edit(
                    account_id=account_id,
                    chat_id=chat_id,
                    message_id=event.message.id,
                    new_text=new_text,
                    edited_at=datetime.now().astimezone(),
                )
                await session.commit()

            if updated and old_text != new_text:
                asyncio.create_task(
                    NotifierService.notify_edited_message(
                        bot=ctx.bot,
                        bot_chat_id=ctx.bot_chat_id,
                        owner_telegram_id=ctx.owner_telegram_id,
                        client=client,
                        message=updated,
                        old_text=old_text,
                    )
                )
        except Exception:
            logger.exception(
                "Failed handling edit account=%s chat=%s msg=%s",
                account_id,
                chat_id,
                event.message.id,
            )
