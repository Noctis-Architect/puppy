from __future__ import annotations

import re
from collections.abc import Awaitable, Callable

from telethon import TelegramClient
from telethon.tl.types import KeyboardButtonCallback, ReplyInlineMarkup

from app.services.anonymous_reveal.callback_decoder import extract_user_id_from_callback
from app.services.anonymous_reveal.models import ScanResult

BOT_USERNAME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{4,31}$")
DEFAULT_MAX_MESSAGES = 500
KNOWN_ANON_BOTS = frozenset(
    {
        "xbchatbot",
        "anonchatbot",
        "anonymouschatbot",
        "hidechatbot",
    }
)
PROGRESS_EVERY_MESSAGES = 25

ScanProgressCallback = Callable[[int, int, bool, str], Awaitable[None]]


def normalize_bot_username(username: str) -> str:
    cleaned = username.strip().lstrip("@").lower()
    if not cleaned:
        raise ValueError("یوزرنیم ربات خالی است.")
    if not BOT_USERNAME_PATTERN.fullmatch(cleaned):
        raise ValueError("فرمت یوزرنیم ربات نامعتبر است.")
    return cleaned


def _extract_all_from_message(message) -> list[ScanResult]:
    markup = message.reply_markup
    if not isinstance(markup, ReplyInlineMarkup):
        return []

    found: list[ScanResult] = []
    for row in markup.rows:
        for button in row.buttons:
            if not isinstance(button, KeyboardButtonCallback) or not button.data:
                continue
            extracted = extract_user_id_from_callback(button.data)
            if extracted is None:
                continue
            decoded_callback, user_id = extracted
            found.append(
                ScanResult(
                    message_id=message.id,
                    button_text=button.text or "",
                    decoded_callback=decoded_callback,
                    user_id=user_id,
                )
            )
    return found


async def scan_all_sender_ids(
    client: TelegramClient,
    bot_username: str,
    *,
    max_messages: int = DEFAULT_MAX_MESSAGES,
    on_progress: ScanProgressCallback | None = None,
) -> tuple[list[ScanResult], int, bool]:
    normalized = normalize_bot_username(bot_username)
    if on_progress:
        await on_progress(0, 0, False, "در حال پیدا کردن ربات…")

    entity = await client.get_entity(normalized)

    if on_progress:
        await on_progress(0, 0, False, "در حال دریافت پیام‌ها از تلگرام…")

    messages = await client.get_messages(entity, limit=max_messages)

    unique: list[ScanResult] = []
    seen_user_ids: set[int] = set()
    messages_scanned = len(messages)
    hit_limit = messages_scanned >= max_messages

    for index, message in enumerate(messages, start=1):
        for result in _extract_all_from_message(message):
            if result.user_id in seen_user_ids:
                continue
            seen_user_ids.add(result.user_id)
            unique.append(result)

        if on_progress and (
            index == 1 or index % PROGRESS_EVERY_MESSAGES == 0 or index == messages_scanned
        ):
            await on_progress(index, len(unique), hit_limit, "در حال بررسی دکمه‌ها…")

    if on_progress:
        await on_progress(messages_scanned, len(unique), hit_limit, "اسکن تمام شد")

    return unique, messages_scanned, hit_limit
