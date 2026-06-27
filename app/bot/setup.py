from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import AppConfig
from app.bot.handlers import admin as admin_handlers
from app.bot.handlers import anonymous_reveal as anonymous_reveal_handlers
from app.bot.handlers import deleted_messages as deleted_messages_handlers
from app.bot.handlers import register as register_handlers
from app.bot.handlers import start as start_handlers
from app.bot.middleware import build_middlewares
from app.bot.service_context import ServiceContext

logger = logging.getLogger(__name__)


def create_bot(config: AppConfig) -> Bot:
    return Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher(
    *,
    config: AppConfig,
    session_factory: async_sessionmaker[AsyncSession],
    service_context: ServiceContext | None = None,
) -> Dispatcher:
    dispatcher = Dispatcher(storage=MemoryStorage())
    for middleware in build_middlewares(
        config=config,
        session_factory=session_factory,
        service_context=service_context,
    ):
        dispatcher.update.middleware(middleware)

    anonymous_reveal_handlers.register(dispatcher)
    admin_handlers.register(dispatcher)
    start_handlers.register(dispatcher)
    register_handlers.register(dispatcher)
    deleted_messages_handlers.register(dispatcher)
    return dispatcher


async def run_bot(bot: Bot, dispatcher: Dispatcher) -> None:
    logger.info("Starting Telegram bot polling...")
    await dispatcher.start_polling(bot, handle_as_tasks=True)
