from __future__ import annotations

import asyncio
import logging

from telethon import events

from app.core.module_api import TelethonContext
from app.modules.contact_tracking.repository import ContactTrackingRepository
from app.modules.settings.repository import TrackedTargetRepository

logger = logging.getLogger(__name__)


def register_events(ctx: TelethonContext) -> None:
    client = ctx.client
    account_id = ctx.account_id
    session_factory = ctx.session_factory

    @client.on(events.UserUpdate())
    async def on_user_update(event: events.UserUpdate.Event) -> None:
        user_id = event.user_id
        if not user_id:
            return

        try:
            from app.modules.settings.repository import AccountSettingsRepository

            async with session_factory() as session:
                settings = await AccountSettingsRepository(session).get_or_create(account_id)
                if not settings.track_presence:
                    return
                if not await TrackedTargetRepository(session).is_tracked(
                    account_id=account_id, target_user_id=user_id
                ):
                    return

                status = "online" if getattr(event, "online", False) else "offline"
                await ContactTrackingRepository(session).add_presence(
                    account_id=account_id,
                    target_user_id=user_id,
                    status=status,
                )
                await session.commit()

            if ctx.bot and ctx.bot_chat_id and getattr(event, "online", False):
                await ctx.bot.send_message(
                    ctx.bot_chat_id,
                    f"🟢 <code>{user_id}</code> آنلاین شد.",
                    protect_content=True,
                )
        except Exception:
            logger.debug("Presence tracking failed", exc_info=True)
