from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from app.config import AppConfig

logger = logging.getLogger(__name__)


def is_super_admin(user_id: int, config: AppConfig) -> bool:
    return config.super_admin_id > 0 and user_id == config.super_admin_id


async def delete_sensitive_message(message: Message) -> None:
    try:
        await message.delete()
    except Exception:
        logger.debug("Could not delete sensitive message chat_id=%s", message.chat.id)


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, *, max_per_minute: int = 30) -> None:
        self._max_per_minute = max_per_minute
        self._hits: dict[int, list[float]] = defaultdict(list)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message) or not event.from_user:
            return await handler(event, data)

        config: AppConfig | None = data.get("config")
        user_id = event.from_user.id
        if config and is_super_admin(user_id, config):
            return await handler(event, data)

        now = time.monotonic()
        hits = self._hits[user_id]
        hits[:] = [t for t in hits if now - t < 60]
        if len(hits) >= self._max_per_minute:
            await event.answer("⏳ درخواست‌های زیاد. لطفاً یک دقیقه صبر کنید.")
            return None

        hits.append(now)
        return await handler(event, data)
