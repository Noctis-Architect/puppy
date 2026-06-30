from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from aiogram import Bot
    from app.telegram.pool import ClientPool

from aiogram import Router
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from telethon import TelegramClient

from app.config import AppConfig

MenuSection = Literal["main", "registered", "admin"]

LightMigrationFn = Callable[[Any], None]
RegisterEventsFn = Callable[["TelethonContext"], None]
RegisterJobsFn = Callable[["JobContext"], None]


@dataclass(frozen=True, slots=True)
class MenuButton:
    text: str
    section: MenuSection = "registered"
    order: int = 100


@dataclass(frozen=True, slots=True)
class TelethonContext:
    client: TelegramClient
    account_id: int
    owner_telegram_id: int
    bot_chat_id: int | None
    session_factory: async_sessionmaker[AsyncSession]
    config: AppConfig
    bot: Bot | None = None


@dataclass(frozen=True, slots=True)
class JobContext:
    scheduler: AsyncIOScheduler
    pool: ClientPool
    session_factory: async_sessionmaker[AsyncSession]
    config: AppConfig
    bot: Bot | None = None


@dataclass(slots=True)
class BotModule:
    name: str
    order: int = 100
    routers: list[Router] = field(default_factory=list)
    menu_buttons: list[MenuButton] = field(default_factory=list)
    register_events: RegisterEventsFn | None = None
    register_jobs: RegisterJobsFn | None = None
    light_migrations: LightMigrationFn | None = None
