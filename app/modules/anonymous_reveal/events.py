from __future__ import annotations

import asyncio
import logging

from telethon import events

from app.core.module_api import TelethonContext
from app.services.anonymous_reveal.bot_scanner import _extract_all_from_message
from app.services.anonymous_reveal.usinfo_lookup import lookup_user_by_id

logger = logging.getLogger(__name__)


def register_events(ctx: TelethonContext) -> None:
    client = ctx.client

    @client.on(events.NewMessage(incoming=True))
    async def on_anon_bot_message(event: events.NewMessage.Event) -> None:
        if not event.is_private or event.out:
            return

        sender = await event.get_sender()
        if not sender or not getattr(sender, "bot", False):
            return

        username = (getattr(sender, "username", None) or "").lower()
        if username not in {
            "xbchatbot",
            "anonchatbot",
            "anonymouschatbot",
            "hidechatbot",
        }:
            return

        try:
            from app.modules.settings.repository import AccountSettingsRepository

            async with ctx.session_factory() as session:
                settings = await AccountSettingsRepository(session).get_or_create(
                    ctx.account_id
                )
                if not settings.auto_anon_reveal:
                    return
        except Exception:
            pass

        found = _extract_all_from_message(event.message)
        if not found:
            return

        best = found[0]
        try:
            lookup = await lookup_user_by_id(client, best.user_id)
            name = lookup.display_name or "-"
            uname = f"@{lookup.username}" if lookup.username else "(بدون یوزرنیم)"
            text = (
                "🔍 <b>شناسایی خودکار پیام ناشناس</b>\n\n"
                f"🤖 از: @{username}\n"
                f"🆔 <code>{best.user_id}</code>\n"
                f"👤 {uname}\n"
                f"📛 {name}"
            )
            if ctx.bot and ctx.bot_chat_id:
                await ctx.bot.send_message(
                    ctx.bot_chat_id,
                    text,
                    protect_content=True,
                )
        except Exception:
            logger.debug("Auto anon reveal failed", exc_info=True)
