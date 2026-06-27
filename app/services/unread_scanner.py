from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from telethon import TelegramClient

from app.services.message_service import MessageService
from app.telegram.pool import ClientPool

logger = logging.getLogger(__name__)

_SCAN_MESSAGE_LIMIT = 50


async def scan_account_unread(
    client: TelegramClient,
    *,
    account_id: int,
    session_factory: async_sessionmaker[AsyncSession],
) -> int:
    stored = 0
    async with session_factory() as session:
        service = MessageService(session)
        async for dialog in client.iter_dialogs():
            if not dialog.is_user:
                continue

            read_inbox_max = dialog.dialog.read_inbox_max_id or 0
            try:
                messages = await client.get_messages(dialog.entity, limit=_SCAN_MESSAGE_LIMIT)
            except Exception:
                logger.debug(
                    "Could not fetch messages account=%s chat=%s",
                    account_id,
                    dialog.id,
                    exc_info=True,
                )
                continue

            for message in messages:
                if message.out or not message.id:
                    continue
                is_read = message.id <= read_inbox_max
                await service.store_message(
                    account_id=account_id,
                    message=message,
                    is_read=is_read,
                )
                stored += 1
        await session.commit()

    return stored


async def scan_all_accounts(
    pool: ClientPool,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    if not pool.clients:
        return

    for account_id, managed in list(pool.clients.items()):
        try:
            count = await scan_account_unread(
                managed.client,
                account_id=account_id,
                session_factory=session_factory,
            )
            if count:
                logger.debug(
                    "Unread scan account=%s processed=%s message(s) at %s",
                    account_id,
                    count,
                    datetime.now().astimezone().isoformat(),
                )
        except Exception:
            logger.exception("Unread scan failed for account=%s", account_id)
