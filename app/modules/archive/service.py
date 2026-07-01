from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.archive.models import StoredMessage
from app.modules.archive.repository import MessageRepository
from app.telegram.utils import extract_message_text, format_sender_name, is_bot_entity
from telethon.tl.custom.message import Message


logger = logging.getLogger(__name__)


async def persist_incoming_message(
    *,
    client,
    session_factory: async_sessionmaker[AsyncSession],
    account_id: int,
    message: Message,
    media_dir: Path,
    check_tracked_skip: bool = True,
    is_read: bool = False,
    read_at: datetime | None = None,
) -> None:
    """Download media (if any) first, then save the message with media already attached.

    Media must be downloaded *before* the row is written: a deletion (especially of
    view-once/self-destructing media, this bot's whole purpose) can arrive within
    milliseconds of the message itself. If we stored the text first and attached
    media afterwards in a second commit, a fast deletion could be processed in the
    gap between the two writes and the alert would go out with no media attached.
    """
    sender = await message.get_sender()
    if is_bot_entity(sender):
        return

    sender_id = sender.id if sender else message.chat_id
    archive_media = True

    async with session_factory() as session:
        if check_tracked_skip:
            from app.modules.settings.repository import TrackedTargetRepository

            target = await TrackedTargetRepository(session).get_target(
                account_id=account_id,
                target_user_id=sender_id,
            )
            if target is not None and not target.track_messages:
                return

        if message.media:
            from app.modules.settings.repository import AccountSettingsRepository

            settings = await AccountSettingsRepository(session).get_or_create(account_id)
            archive_media = settings.archive_media

    media_type: str | None = None
    media_path: str | None = None
    if message.media:
        media_type, media_path = await MediaArchiveService.maybe_download(
            client=client,
            message=message,
            account_id=account_id,
            media_dir=media_dir,
            archive_media=archive_media,
        )

    async with session_factory() as session:
        await MessageService(session).store_incoming(
            account_id=account_id,
            message=message,
            is_read=is_read,
            read_at=read_at,
            media_type=media_type,
            media_path=media_path,
            sender=sender,
        )
        await session.commit()


class MessageService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = MessageRepository(session)

    async def store_incoming(
        self,
        *,
        account_id: int,
        message: Message,
        is_read: bool = False,
        read_at: datetime | None = None,
        media_type: str | None = None,
        media_path: str | None = None,
        sender=None,
    ) -> None:
        if sender is None:
            sender = await message.get_sender()
        if is_bot_entity(sender):
            return
        sender_id = sender.id if sender else message.chat_id
        await self._repo.upsert_incoming(
            account_id=account_id,
            chat_id=message.chat_id,
            sender_id=sender_id,
            message_id=message.id,
            text=extract_message_text(message),
            sender_name=format_sender_name(message),
            received_at=message.date.replace(tzinfo=message.date.tzinfo)
            if message.date
            else datetime.now().astimezone(),
            is_read=is_read,
            read_at=read_at,
            media_type=media_type,
            media_path=media_path,
        )

    async def store_message(
        self,
        *,
        account_id: int,
        message: Message,
        is_read: bool,
        media_type: str | None = None,
        media_path: str | None = None,
    ) -> None:
        read_at = datetime.now().astimezone() if is_read else None
        await self.store_incoming(
            account_id=account_id,
            message=message,
            is_read=is_read,
            read_at=read_at,
            media_type=media_type,
            media_path=media_path,
        )


async def with_message_service(
    factory: async_sessionmaker[AsyncSession],
    callback,
):
    async with factory() as session:
        service = MessageService(session)
        result = await callback(service)
        await session.commit()
        return result


class MediaArchiveService:
    @staticmethod
    def _is_ephemeral(message: Message) -> bool:
        if getattr(message, "ttl_period", None):
            return True
        media = message.media
        if media is None:
            return False
        if getattr(media, "ttl_seconds", None):
            return True
        media_name = type(media).__name__.lower()
        return "once" in media_name or "ttl" in media_name

    @staticmethod
    async def maybe_download(
        *,
        client,
        message: Message,
        account_id: int,
        media_dir: Path,
        archive_media: bool = True,
    ) -> tuple[str | None, str | None]:
        if not message.media:
            return None, None
        if not MediaArchiveService._is_ephemeral(message) and not archive_media:
            return None, None

        media_dir.mkdir(parents=True, exist_ok=True)
        target = media_dir / f"{account_id}_{message.chat_id}_{message.id}"
        try:
            path = await client.download_media(message, file=str(target))
            if not path:
                logger.warning(
                    "Media download returned empty path account=%s chat=%s msg=%s",
                    account_id,
                    message.chat_id,
                    message.id,
                )
                return None, None
            return type(message.media).__name__, str(path)
        except Exception:
            logger.warning(
                "Media download failed account=%s chat=%s msg=%s",
                account_id,
                message.chat_id,
                message.id,
                exc_info=True,
            )
            return None, None
