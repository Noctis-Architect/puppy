from __future__ import annotations

import logging

from telethon import events

from app.core.module_api import TelethonContext
from app.services.anonymous_reveal.bot_scanner import KNOWN_ANON_BOTS, _extract_all_from_message
from app.services.anonymous_reveal.callback_decoder import pick_best_callback
from app.services.anonymous_reveal.usinfo_lookup import lookup_user_by_id

logger = logging.getLogger(__name__)


def _format_auto_reveal(
    *,
    bot_username: str,
    user_id: int,
    username: str | None,
    display_name: str | None,
    phone: str | None,
    lookup_failed: bool,
) -> str:
    uname = f"@{username}" if username else "(بدون یوزرنیم)"
    name = display_name or "-"
    phone_line = phone if phone else "(در دسترس نیست)"
    lines = [
        "🔍 <b>شناسایی خودکار پیام ناشناس</b>",
        "",
        f"🤖 از: @{bot_username}",
        f"🆔 <code>{user_id}</code>",
        f"👤 {uname}",
        f"📛 {name}",
        f"📱 {phone_line}",
    ]
    if lookup_failed:
        lines.append("")
        lines.append("⚠️ usinfobot: ناموفق — فقط آیدی از دکمهٔ ربات استخراج شد.")
    return "\n".join(lines)


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
        if username not in KNOWN_ANON_BOTS:
            return

        found = _extract_all_from_message(event.message)
        if not found:
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
            logger.warning(
                "Could not load settings for auto anon reveal account=%s",
                ctx.account_id,
                exc_info=True,
            )
            return

        best = pick_best_callback(
            [(item.decoded_callback, item.user_id, item.button_text) for item in found]
        )
        if best is None:
            return

        _decoded, user_id, _button_text = best
        lookup_failed = False
        lookup_username: str | None = None
        lookup_name: str | None = None
        lookup_phone: str | None = None

        try:
            lookup = await lookup_user_by_id(client, user_id)
            lookup_username = lookup.username
            lookup_name = lookup.display_name
            lookup_phone = lookup.phone
        except Exception:
            lookup_failed = True
            logger.warning(
                "Auto anon reveal lookup failed user_id=%s bot=@%s",
                user_id,
                username,
                exc_info=True,
            )

        text = _format_auto_reveal(
            bot_username=username,
            user_id=user_id,
            username=lookup_username,
            display_name=lookup_name,
            phone=lookup_phone,
            lookup_failed=lookup_failed,
        )
        if ctx.bot and ctx.bot_chat_id:
            await ctx.bot.send_message(
                ctx.bot_chat_id,
                text,
                protect_content=True,
            )
        else:
            await client.send_message("me", text)
