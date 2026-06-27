from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.security import RateLimitMiddleware
from app.bot.service_context import ServiceContext
from app.config import AppConfig


class AppContextMiddleware(BaseMiddleware):
    def __init__(
        self,
        *,
        config: AppConfig,
        session_factory: async_sessionmaker[AsyncSession],
        service_context: ServiceContext | None = None,
    ) -> None:
        self.config = config
        self.session_factory = session_factory
        self.service_context = service_context

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["config"] = self.config
        data["session_factory"] = self.session_factory
        if self.service_context is not None:
            data["service_context"] = self.service_context
        return await handler(event, data)


def build_middlewares(
    *,
    config: AppConfig,
    session_factory: async_sessionmaker[AsyncSession],
    service_context: ServiceContext | None = None,
) -> list[BaseMiddleware]:
    return [
        RateLimitMiddleware(max_per_minute=30),
        AppContextMiddleware(
            config=config,
            session_factory=session_factory,
            service_context=service_context,
        ),
    ]
