from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from telethon import TelegramClient

from app.bot.concurrency import account_client_busy
from app.modules.archive.service import persist_incoming_message
from app.modules.settings.repository import AccountSettingsRepository
from app.telegram.client_utils import SessionExpiredError, ensure_client_connected
from app.telegram.pool import ClientPool
from app.telegram.utils import is_bot_entity

logger = logging.getLogger(__name__)

_SCAN_MESSAGE_LIMIT = 50
_DIALOGS_PER_RUN = 15


async def scan_account_unread(
    client: TelegramClient,
    *,
    account_id: int,
    session_factory: async_sessionmaker[AsyncSession],
    media_dir,
    max_dialogs: int = _DIALOGS_PER_RUN,
) -> int:
    stored = 0
    dialogs_seen = 0

    async for dialog in client.iter_dialogs():
        if not dialog.is_user:
            continue

        dialogs_seen += 1
        if dialogs_seen > max_dialogs:
            break

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
            if is_bot_entity(await message.get_sender()):
                continue
            is_read = message.id <= read_inbox_max
            read_at = datetime.now().astimezone() if is_read else None
            try:
                await persist_incoming_message(
                    client=client,
                    session_factory=session_factory,
                    account_id=account_id,
                    message=message,
                    media_dir=media_dir,
                    is_read=is_read,
                    read_at=read_at,
                )
                stored += 1
            except Exception:
                logger.debug(
                    "Unread scan store failed account=%s chat=%s msg=%s",
                    account_id,
                    message.chat_id,
                    message.id,
                    exc_info=True,
                )

    return stored


async def scan_all_accounts(
    pool: ClientPool,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    media_dir,
) -> None:
    if not pool.clients:
        return

    for account_id, managed in list(pool.clients.items()):
        if account_client_busy(account_id):
            logger.debug(
                "Unread scan skipped for account=%s: user operation in progress",
                account_id,
            )
            continue

        try:
            try:
                await ensure_client_connected(managed.client)
            except SessionExpiredError:
                logger.warning("Unread scan skipped for account=%s: session expired", account_id)
                continue

            count = await scan_account_unread(
                managed.client,
                account_id=account_id,
                session_factory=session_factory,
                media_dir=media_dir,
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
