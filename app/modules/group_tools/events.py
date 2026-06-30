from __future__ import annotations

import asyncio
import logging

from telethon import events

from app.core.module_api import TelethonContext
from app.modules.archive.service import persist_incoming_message
from app.modules.settings.repository import MonitoredChatRepository

logger = logging.getLogger(__name__)


def register_events(ctx: TelethonContext) -> None:
    client = ctx.client
    account_id = ctx.account_id
    session_factory = ctx.session_factory

    async def _store_group_message(message) -> None:
        chat_id = message.chat_id
        if chat_id is None or chat_id >= 0:
            return

        async with session_factory() as session:
            if not await MonitoredChatRepository(session).is_monitored(
                account_id=account_id, chat_id=chat_id
            ):
                return

        try:
            await persist_incoming_message(
                client=client,
                session_factory=session_factory,
                account_id=account_id,
                message=message,
                media_dir=ctx.config.media_dir,
                check_tracked_skip=False,
            )
        except Exception:
            logger.exception(
                "Failed storing group message account=%s chat=%s msg=%s",
                account_id,
                chat_id,
                message.id,
            )

    @client.on(events.NewMessage())
    async def on_group_message(event: events.NewMessage.Event) -> None:
        if event.out or event.is_private:
            return
        if not event.is_group:
            return
        asyncio.create_task(_store_group_message(event.message))

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
