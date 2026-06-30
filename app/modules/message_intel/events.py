from __future__ import annotations

import logging
from datetime import datetime

from telethon import events

from app.core.module_api import TelethonContext
from app.modules.archive.notifier import NotifierService
from app.modules.archive.repository import MessageRepository
from app.modules.settings.repository import MonitoredChatRepository
from app.telegram.client_utils import resolve_event_message
from app.telegram.utils import extract_message_text, is_bot_entity

logger = logging.getLogger(__name__)


async def _should_track_edit(session_factory, account_id: int, chat_id: int) -> bool:
    from app.modules.settings.repository import AccountSettingsRepository

    async with session_factory() as session:
        settings = await AccountSettingsRepository(session).get_or_create(account_id)
        if not settings.track_edits:
            return False
        if chat_id < 0:
            return await MonitoredChatRepository(session).saves_edits(
                account_id=account_id, chat_id=chat_id
            )
        return True


def register_events(ctx: TelethonContext) -> None:
    client = ctx.client
    account_id = ctx.account_id
    session_factory = ctx.session_factory

    @client.on(events.MessageEdited())
    async def on_message_edited(event: events.MessageEdited.Event) -> None:
        chat_id = event.chat_id
        message_id = event.message.id
        if chat_id is None or not message_id:
            return

        try:
            if not await _should_track_edit(session_factory, account_id, chat_id):
                return

            message = await resolve_event_message(client, chat_id, message_id)
            if message is None:
                return

            sender = await message.get_sender()
            if is_bot_entity(sender):
                return

            new_text = extract_message_text(message)
            async with session_factory() as session:
                repo = MessageRepository(session)
                existing = await repo.get_by_id(
                    account_id=account_id,
                    chat_id=chat_id,
                    message_id=message_id,
                )
                if not existing:
                    return
                old_text = existing.text
                updated = await repo.record_edit(
                    account_id=account_id,
                    chat_id=chat_id,
                    message_id=message_id,
                    new_text=new_text,
                    edited_at=datetime.now().astimezone(),
                )
                await session.commit()

            if updated and old_text != new_text:
                await NotifierService.notify_edited_message(
                    bot=ctx.bot,
                    bot_chat_id=ctx.bot_chat_id,
                    owner_telegram_id=ctx.owner_telegram_id,
                    client=client,
                    message=updated,
                    old_text=old_text,
                )
        except Exception:
            logger.exception(
                "Failed handling edit account=%s chat=%s msg=%s",
                account_id,
                chat_id,
                message_id,
            )
