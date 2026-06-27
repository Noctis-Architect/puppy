from __future__ import annotations

import re

from telethon import TelegramClient
from telethon.tl.types import KeyboardButtonCallback, ReplyInlineMarkup

from app.services.anonymous_reveal.callback_decoder import extract_user_id_from_callback
from app.services.anonymous_reveal.models import ScanResult

BOT_USERNAME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{4,31}$")


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
) -> tuple[list[ScanResult], int]:
    normalized = normalize_bot_username(bot_username)
    entity = await client.get_entity(normalized)

    unique: list[ScanResult] = []
    seen_user_ids: set[int] = set()
    messages_scanned = 0

    async for message in client.iter_messages(entity):
        messages_scanned += 1
        for result in _extract_all_from_message(message):
            if result.user_id in seen_user_ids:
                continue
            seen_user_ids.add(result.user_id)
            unique.append(result)

    return unique, messages_scanned
