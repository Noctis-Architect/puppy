from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from telethon import TelegramClient

from app.config import AppConfig
from app.core.loader import get_modules
from app.core.module_api import TelethonContext

logger = logging.getLogger(__name__)


def register_account_events(
    *,
    client: TelegramClient,
    account_id: int,
    owner_telegram_id: int,
    session_factory: async_sessionmaker[AsyncSession],
    config: AppConfig,
    bot: Bot | None = None,
    bot_chat_id: int | None = None,
) -> None:
    ctx = TelethonContext(
        client=client,
        account_id=account_id,
        owner_telegram_id=owner_telegram_id,
        bot_chat_id=bot_chat_id,
        session_factory=session_factory,
        config=config,
        bot=bot,
    )
    for module in get_modules():
        if module.register_events is not None:
            module.register_events(ctx)


# Backward compatibility alias
register_handlers = register_account_events
