from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from telethon import TelegramClient

from app.bot.concurrency import account_client_lock
from app.modules.archive.service import MediaArchiveService, MessageService
from app.modules.settings.repository import AccountSettingsRepository
from app.telegram.client_utils import SessionExpiredError, ensure_client_connected
from app.telegram.pool import ClientPool
from app.telegram.utils import is_bot_entity

logger = logging.getLogger(__name__)

_SCAN_MESSAGE_LIMIT = 50
_DIALOGS_PER_RUN = 25


async def scan_account_unread(
    client: TelegramClient,
    *,
    account_id: int,
    session_factory: async_sessionmaker[AsyncSession],
    media_dir: Path,
    max_dialogs: int = _DIALOGS_PER_RUN,
) -> int:
    stored = 0
    dialogs_seen = 0

    async with session_factory() as session:
        settings = await AccountSettingsRepository(session).get_or_create(account_id)
        archive_media = settings.archive_media

    async with session_factory() as session:
        service = MessageService(session)
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

                media_type = None
                media_path = None
                if message.media:
                    media_type, media_path = await MediaArchiveService.maybe_download(
                        client=client,
                        message=message,
                        account_id=account_id,
                        media_dir=media_dir,
                        archive_media=archive_media,
                    )

                await service.store_message(
                    account_id=account_id,
                    message=message,
                    is_read=is_read,
                    media_type=media_type,
                    media_path=media_path,
                )
                stored += 1
        await session.commit()

    return stored


async def scan_all_accounts(
    pool: ClientPool,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    media_dir: Path,
) -> None:
    if not pool.clients:
        return

    for account_id, managed in list(pool.clients.items()):
        lock = account_client_lock(account_id)
        if lock.locked():
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

            async with lock:
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
