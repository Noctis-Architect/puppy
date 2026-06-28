from __future__ import annotations

import logging

from telethon import TelegramClient

logger = logging.getLogger(__name__)


class SessionExpiredError(RuntimeError):
    """Telethon session is no longer authorized."""


async def ensure_client_connected(client: TelegramClient) -> None:
    if client.is_connected():
        return

    logger.info("Reconnecting disconnected Telethon client...")
    await client.connect()
    if not await client.is_user_authorized():
        raise SessionExpiredError("Telethon session expired")


def message_text(message) -> str:
    if message is None:
        return ""

    raw = getattr(message, "raw_text", None)
    if raw:
        return raw

    text = getattr(message, "text", None)
    if text:
        return text

    body = getattr(message, "message", None)
    if isinstance(body, str):
        return body
    return ""
