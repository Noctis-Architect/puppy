from __future__ import annotations

import logging

from telethon import events

from app.core.module_api import TelethonContext
from app.modules.archive.service import MessageService
from app.modules.settings.repository import MonitoredChatRepository
from app.telegram.client_utils import resolve_event_message
from app.telegram.utils import is_bot_entity

logger = logging.getLogger(__name__)


def register_events(ctx: TelethonContext) -> None:
    client = ctx.client
    account_id = ctx.account_id
    session_factory = ctx.session_factory

    async def _store_group_message(chat_id: int, message_id: int) -> None:
        if chat_id is None or chat_id >= 0:
            return

        async with session_factory() as session:
            if not await MonitoredChatRepository(session).is_monitored(
                account_id=account_id, chat_id=chat_id
            ):
                return

        try:
            message = await resolve_event_message(client, chat_id, message_id)
            if message is None:
                return

            sender = await message.get_sender()
            if is_bot_entity(sender):
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
                "Failed storing group message account=%s chat=%s msg=%s",
                account_id,
                chat_id,
                message_id,
            )

    @client.on(events.NewMessage())
    async def on_group_message(event: events.NewMessage.Event) -> None:
        if event.out or event.is_private:
            return
        if not event.is_group:
            return
        await _store_group_message(event.chat_id, event.message.id)

    @client.on(events.NewMessage())
    async def on_group_mention(event: events.NewMessage.Event) -> None:
        if event.out or event.is_private or not event.is_group:
            return
        if not event.message.mentioned:
            return

        chat_id = event.chat_id
        if chat_id is None:
            return

        try:
            from app.modules.settings.repository import AccountSettingsRepository

            async with session_factory() as session:
                if not await MonitoredChatRepository(session).is_listed(
                    account_id=account_id, chat_id=chat_id
                ):
                    return
                settings = await AccountSettingsRepository(session).get_or_create(account_id)
                if not settings.group_mention_alerts:
                    return

            sender = await event.get_sender()
            name = getattr(sender, "first_name", None) or "کاربر"
            text = (
                "📣 <b>منشن در گروه</b>\n\n"
                f"👥 گروه: <code>{chat_id}</code>\n"
                f"👤 {name}\n"
                f"📝 {(event.message.text or '')[:200]}"
            )
            if ctx.bot and ctx.bot_chat_id:
                await ctx.bot.send_message(ctx.bot_chat_id, text, protect_content=True)
        except Exception:
            logger.debug("Group mention alert failed", exc_info=True)

    @client.on(events.ChatAction())
    async def on_chat_action(event: events.ChatAction.Event) -> None:
        chat_id = event.chat_id
        if chat_id is None or chat_id >= 0:
            return

        try:
            from app.modules.settings.repository import AccountSettingsRepository

            async with session_factory() as session:
                if not await MonitoredChatRepository(session).is_listed(
                    account_id=account_id, chat_id=chat_id
                ):
                    return
                settings = await AccountSettingsRepository(session).get_or_create(account_id)
                if not settings.group_member_alerts:
                    return

            action = None
            if event.user_joined or event.user_added:
                action = "عضو جدید"
            elif event.user_left or event.user_kicked:
                action = "خروج عضو"
            if not action:
                return

            user = await event.get_user()
            name = getattr(user, "first_name", None) or str(event.user_id)
            text = f"👥 <b>{action}</b> در گروه <code>{chat_id}</code>\n👤 {name}"
            if ctx.bot and ctx.bot_chat_id:
                await ctx.bot.send_message(ctx.bot_chat_id, text, protect_content=True)
        except Exception:
            logger.debug("Chat action alert failed", exc_info=True)
