from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from aiogram import Bot
from telethon import TelegramClient

from app.config import AppConfig
from app.db.models import Account
from app.handlers.registry import register_handlers
from app.repositories.account_repo import AccountRepository
from app.telegram.factory import connect_client
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ManagedClient:
    account: Account
    client: TelegramClient


@dataclass
class ClientPool:
    config: AppConfig
    session_factory: async_sessionmaker[AsyncSession]
    bot: Bot | None = None
    clients: dict[int, ManagedClient] = field(default_factory=dict)

    async def start_all(self) -> None:
        async with self.session_factory() as db:
            accounts = await AccountRepository(db).list_active()

        if not accounts:
            logger.warning("No active accounts found. Use bot registration or: python main.py add-user")
            return

        results = await asyncio.gather(
            *(self.start_account(account) for account in accounts),
            return_exceptions=True,
        )
        for account, result in zip(accounts, results):
            if isinstance(result, Exception):
                logger.error(
                    "Failed starting account id=%s: %s",
                    account.id,
                    result,
                )

    async def start_account(self, account: Account) -> ManagedClient:
        if account.id in self.clients:
            return self.clients[account.id]

        logger.info(
            "Starting client for account id=%s telegram_id=%s",
            account.id,
            account.telegram_id,
        )
        client = await connect_client(self.config, account.session_path)
        if not await client.is_user_authorized():
            await client.disconnect()
            raise RuntimeError(f"Session expired for account {account.id}")

        register_handlers(
            client=client,
            account_id=account.id,
            owner_telegram_id=account.telegram_id,
            session_factory=self.session_factory,
            bot=self.bot,
            bot_chat_id=account.bot_chat_id or account.telegram_id,
        )

        managed = ManagedClient(account=account, client=client)
        self.clients[account.id] = managed
        return managed

    async def stop_account(self, account_id: int) -> None:
        managed = self.clients.pop(account_id, None)
        if managed is not None:
            await managed.client.disconnect()
            logger.info("Stopped monitoring for account id=%s", account_id)

    async def stop_all(self) -> None:
        for managed in list(self.clients.values()):
            await managed.client.disconnect()
        self.clients.clear()

    async def run_forever(self) -> None:
        await self.start_all()
        if not self.clients:
            raise SystemExit(1)

        logger.info("Monitoring %s account(s). Press Ctrl+C to stop.", len(self.clients))
        await self.clients[next(iter(self.clients))].client.run_until_disconnected()
