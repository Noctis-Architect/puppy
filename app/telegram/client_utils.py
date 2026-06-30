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


async def resolve_event_message(client: TelegramClient, chat_id: int, message_id: int):
    """Re-fetch a message by id so work is not done on a stale Telethon event object."""
    if not message_id:
        return None
    try:
        result = await client.get_messages(chat_id, ids=message_id)
    except Exception:
        logger.debug(
            "Could not re-fetch message chat=%s id=%s",
            chat_id,
            message_id,
            exc_info=True,
        )
        return None
    if result is None:
        return None
    if isinstance(result, list):
        return result[0] if result else None
    return result


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
