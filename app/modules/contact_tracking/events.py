from __future__ import annotations

import asyncio
import logging

from telethon import events
from telethon.tl.types import UpdateUserTyping, UserStatusOnline

from app.core.module_api import TelethonContext
from app.modules.contact_tracking.repository import ContactTrackingRepository
from app.modules.settings.repository import AccountSettingsRepository, TrackedTargetRepository

logger = logging.getLogger(__name__)


def register_events(ctx: TelethonContext) -> None:
    client = ctx.client
    account_id = ctx.account_id
    session_factory = ctx.session_factory

    async def _handle_user_update(event: events.UserUpdate.Event) -> None:
        user_id = event.user_id
        if not user_id or event.status is None:
            return

        try:
            async with session_factory() as session:
                settings = await AccountSettingsRepository(session).get_or_create(account_id)
                if not settings.track_presence:
                    return
                target = await TrackedTargetRepository(session).get_target(
                    account_id=account_id,
                    target_user_id=user_id,
                )
                if target is None or not target.track_presence:
                    return

                is_online = isinstance(event.status, UserStatusOnline)
                status = "online" if is_online else "offline"
                await ContactTrackingRepository(session).add_presence(
                    account_id=account_id,
                    target_user_id=user_id,
                    status=status,
                )
                await session.commit()

            if ctx.bot and ctx.bot_chat_id:
                if is_online:
                    text = f"🟢 <code>{user_id}</code> آنلاین شد."
                else:
                    text = f"⚫ <code>{user_id}</code> آفلاین شد."
                await ctx.bot.send_message(ctx.bot_chat_id, text, protect_content=True)
        except Exception:
            logger.debug("Presence tracking failed", exc_info=True)

    @client.on(events.UserUpdate())
    async def on_user_update(event: events.UserUpdate.Event) -> None:
        asyncio.create_task(_handle_user_update(event))

    async def _handle_user_typing(update: UpdateUserTyping) -> None:
        user_id = update.user_id
        if not user_id:
            return

        try:
            async with session_factory() as session:
                settings = await AccountSettingsRepository(session).get_or_create(account_id)
                if not settings.typing_alerts:
                    return
                target = await TrackedTargetRepository(session).get_target(
                    account_id=account_id,
                    target_user_id=user_id,
                )
                if target is None:
                    return

            if ctx.bot and ctx.bot_chat_id:
                await ctx.bot.send_message(
                    ctx.bot_chat_id,
                    f"⌨️ <code>{user_id}</code> در حال تایپ است.",
                    protect_content=True,
                )
        except Exception:
            logger.debug("Typing alert failed", exc_info=True)

    @client.on(events.Raw(types=UpdateUserTyping))
    async def on_user_typing(update: UpdateUserTyping) -> None:
        asyncio.create_task(_handle_user_typing(update))
