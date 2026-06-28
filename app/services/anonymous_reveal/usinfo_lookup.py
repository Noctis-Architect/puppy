from __future__ import annotations

import asyncio
import logging
import re

from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.types import (
    BotInlineMessageMediaWebPage,
    BotInlineMessageRichMessage,
    BotInlineMessageText,
)

from app.services.anonymous_reveal.models import UserLookup
from app.telegram.client_utils import ensure_client_connected, message_text

logger = logging.getLogger(__name__)

USINFO_BOT = "usinfobot"
LOOKUP_TIMEOUT = 20
INLINE_PEER = "me"

_INVISIBLE_CHARS = re.compile(r"[\u200b\u200c\u200d\u2060\u2063\ufeff\u00ad]+")

_USERNAME_PATTERNS = (
    re.compile(r"🌐\s*@([A-Za-z0-9_]{5,32})", re.I),
    re.compile(
        r"(?:^|\n)(?:Username|یوزر(?:نیم|نیم)|نام کاربری)\s*[:：]\s*@?([A-Za-z0-9_]{5,32})",
        re.I,
    ),
    re.compile(r"(?:^|\n)@([A-Za-z0-9_]{5,32})(?:\s|$)", re.I),
)
_NAME_PATTERNS = (
    re.compile(
        r"(?:👦🏻|👧🏻|👨|👩|🧑(?:\s|\)|🏻))\s*\[([^\]]+)\]\(tg://user\?id=\d+\)",
        re.I,
    ),
    re.compile(r"(?:👦🏻|👧🏻|👨|👩|🧑(?:\s|\)|🏻))\s*([^\n🌐🕑\[@]+)", re.I),
    re.compile(r"(?:^|\n)(?:First name|Last name|Name|نام)\s*[:：]\s*(.+?)(?:\n|$)", re.I),
)
_NO_USERNAME_MARKERS = (
    "no username",
    "without username",
    "doesn't have a username",
    "does not have a username",
    "یوزرنیم ندارد",
    "یوزر ندارد",
    "بدون یوزرنیم",
)
_ID_PATTERNS = (
    re.compile(r"👤\s*`?(\d{5,})`?"),
    re.compile(r"(?:^|\n)(?:ID|Id|آیدی|شناسه)\s*[:：]\s*`?(\d{5,})`?", re.I),
)


def _clean_usinfo_text(text: str) -> str:
    return _INVISIBLE_CHARS.sub("", text).strip()


def _clean_display_name(name: str) -> str:
    cleaned = name.strip()
    markdown_link = re.match(r"\[([^\]]+)\]\(tg://user\?id=\d+\)", cleaned)
    if markdown_link:
        cleaned = markdown_link.group(1)
    cleaned = re.sub(r"__([^_]+)__", r"\1", cleaned)
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
    return cleaned.strip()


def _has_no_username(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _NO_USERNAME_MARKERS)


def _parse_usinfo_response(user_id: int, text: str) -> UserLookup:
    cleaned = _clean_usinfo_text(text)

    username: str | None = None
    for pattern in _USERNAME_PATTERNS:
        match = pattern.search(cleaned)
        if match:
            candidate = match.group(1)
            if candidate.lower() != USINFO_BOT:
                username = candidate
                break

    if username and _has_no_username(cleaned):
        username = None

    display_name: str | None = None
    for pattern in _NAME_PATTERNS:
        match = pattern.search(cleaned)
        if match:
            candidate = _clean_display_name(match.group(1))
            if candidate and not candidate.isdigit():
                display_name = candidate
                break

    return UserLookup(
        user_id=user_id,
        username=username,
        display_name=display_name,
        raw_response=text,
    )


def _response_matches_user(text: str, user_id: int) -> bool:
    cleaned = _clean_usinfo_text(text)
    if not cleaned:
        return False
    if str(user_id) in cleaned:
        return True
    for pattern in _ID_PATTERNS:
        match = pattern.search(cleaned)
        if match and int(match.group(1)) == user_id:
            return True
    return False


def _extract_inline_text(inline_message) -> str:
    if inline_message is None:
        return ""

    if isinstance(inline_message, BotInlineMessageText):
        return inline_message.message or ""

    if isinstance(inline_message, BotInlineMessageMediaWebPage):
        return inline_message.message or ""

    if isinstance(inline_message, BotInlineMessageRichMessage):
        rich = inline_message.rich_message
        if rich and getattr(rich, "blocks", None):
            parts: list[str] = []
            for block in rich.blocks:
                text = getattr(block, "text", None)
                if text:
                    parts.append(text)
            return "\n".join(parts)

    message = getattr(inline_message, "message", None)
    if isinstance(message, str):
        return message
    return ""


def _pick_inline_result(results, user_id: int):
    if not results:
        return None

    uid = str(user_id)
    for result in results:
        blob = " ".join(
            part
            for part in (
                result.title,
                result.description,
                _extract_inline_text(result.message),
            )
            if part
        )
        if uid in blob:
            return result
    return results[0]


def _enrich_from_inline_users(lookup: UserLookup, users, user_id: int) -> UserLookup:
    for user in users or []:
        if user.id != user_id:
            continue
        username = lookup.username or getattr(user, "username", None)
        first = getattr(user, "first_name", None) or ""
        last = getattr(user, "last_name", None) or ""
        display_name = lookup.display_name or " ".join(part for part in (first, last) if part).strip() or None
        return UserLookup(
            user_id=lookup.user_id,
            username=username,
            display_name=display_name,
            raw_response=lookup.raw_response,
        )
    return lookup


async def lookup_user_by_id(
    client: TelegramClient,
    user_id: int,
    *,
    bot_username: str = USINFO_BOT,
    timeout: float = LOOKUP_TIMEOUT,
) -> UserLookup:
    try:
        return await _lookup_once(client, user_id, bot_username=bot_username, timeout=timeout)
    except FloodWaitError as exc:
        logger.warning("FloodWait from usinfobot: %s seconds", exc.seconds)
        await asyncio.sleep(exc.seconds)
        return await _lookup_once(client, user_id, bot_username=bot_username, timeout=timeout)


async def _lookup_once(
    client: TelegramClient,
    user_id: int,
    *,
    bot_username: str,
    timeout: float,
) -> UserLookup:
    await ensure_client_connected(client)

    query = str(user_id)
    results = await asyncio.wait_for(
        client.inline_query(bot_username, query, entity=INLINE_PEER),
        timeout=timeout,
    )

    if not results:
        raise ValueError("usinfobot نتیجه inline برنگرداند.")

    result = _pick_inline_result(results, user_id)
    if result is None:
        raise ValueError("usinfobot نتیجه inline برنگرداند.")

    preview = _extract_inline_text(result.message)
    if _response_matches_user(preview, user_id):
        lookup = _parse_usinfo_response(user_id, preview)
        return _enrich_from_inline_users(lookup, results.users, user_id)

    sent = await asyncio.wait_for(result.click(INLINE_PEER), timeout=timeout)
    text = message_text(sent)

    try:
        await client.delete_messages(INLINE_PEER, sent.id)
    except Exception:
        logger.debug("Could not delete usinfobot lookup message id=%s", sent.id, exc_info=True)

    if not _response_matches_user(text, user_id):
        raise ValueError("پاسخ usinfobot با آیدی درخواستی مطابقت ندارد.")

    lookup = _parse_usinfo_response(user_id, text)
    return _enrich_from_inline_users(lookup, results.users, user_id)
