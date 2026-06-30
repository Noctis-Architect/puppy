from __future__ import annotations

import logging
from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from telethon import TelegramClient
from telethon.tl.functions.users import GetFullUserRequest

from app.modules.contact_tracking.repository import ContactTrackingRepository
from app.modules.contact_tracking.utils import extract_photo_id
from app.telegram.client_utils import ensure_client_connected

logger = logging.getLogger(__name__)


async def _fetch_bio(client: TelegramClient, entity) -> str | None:
    try:
        full = await client(GetFullUserRequest(entity))
        return getattr(full.full_user, "about", None)
    except Exception:
        return getattr(entity, "about", None) or getattr(entity, "bio", None)


async def capture_profile_snapshot(
    *,
    client: TelegramClient,
    session_factory: async_sessionmaker[AsyncSession],
    account_id: int,
    target_user_id: int,
    notify_bot: Bot | None = None,
    notify_chat_id: int | None = None,
) -> list[tuple[str, str | None, str | None]]:
    """Fetch profile, update snapshot, return detected changes (empty on first capture)."""
    await ensure_client_connected(client)
    entity = await client.get_entity(target_user_id)
    display_name = " ".join(
        p for p in (getattr(entity, "first_name", ""), getattr(entity, "last_name", "")) if p
    ).strip() or None
    username = getattr(entity, "username", None)
    bio = await _fetch_bio(client, entity)
    photo_id = extract_photo_id(entity)

    changes: list[tuple[str, str | None, str | None]] = []
    async with session_factory() as session:
        repo = ContactTrackingRepository(session)
        old = await repo.get_snapshot(account_id=account_id, target_user_id=target_user_id)
        snap = await repo.upsert_snapshot(
            account_id=account_id,
            target_user_id=target_user_id,
            display_name=display_name,
            username=username,
            bio=bio,
            photo_id=photo_id,
        )
        if old:
            for field, old_v, new_v in (
                ("name", old.display_name, snap.display_name),
                ("username", old.username, snap.username),
                ("bio", old.bio, snap.bio),
                ("photo", old.photo_id, snap.photo_id),
            ):
                if old_v != new_v:
                    changes.append((field, old_v, new_v))
                    await repo.add_profile_change(
                        account_id=account_id,
                        target_user_id=target_user_id,
                        field=field,
                        old_value=old_v,
                        new_value=new_v,
                    )
        await session.commit()

    if changes and notify_bot and notify_chat_id:
        lines = [f"👤 تغییر پروفایل <code>{target_user_id}</code>", ""]
        for field, old_v, new_v in changes:
            lines.append(f"• {field}: {old_v or '-'} → {new_v or '-'}")
        await notify_bot.send_message(notify_chat_id, "\n".join(lines), protect_content=True)

    return changes


async def archive_story_item(
    *,
    client: TelegramClient,
    session_factory: async_sessionmaker[AsyncSession],
    account_id: int,
    target_user_id: int,
    story,
    media_dir: Path,
    download_media: bool,
    notify_bot: Bot | None = None,
    notify_chat_id: int | None = None,
    mention_note: str = "",
) -> bool:
    story_id = getattr(story, "id", None)
    if not story_id:
        return False

    async with session_factory() as session:
        repo = ContactTrackingRepository(session)
        if await repo.has_story_archived(
            account_id=account_id,
            target_user_id=target_user_id,
            story_id=story_id,
        ):
            return False

    media_path = None
    if download_media:
        try:
            target_path = media_dir / f"{account_id}_{target_user_id}_{story_id}"
            downloaded = await client.download_media(story, file=str(target_path))
            if downloaded:
                media_path = str(downloaded)
        except Exception:
            logger.warning(
                "Story download failed account=%s target=%s story=%s",
                account_id,
                target_user_id,
                story_id,
                exc_info=True,
            )

    async with session_factory() as session:
        await ContactTrackingRepository(session).add_story_archive(
            account_id=account_id,
            target_user_id=target_user_id,
            story_id=story_id,
            media_path=media_path,
        )
        await session.commit()

    if notify_bot and notify_chat_id:
        text = f"📖 استوری جدید از <code>{target_user_id}</code>{mention_note} ذخیره شد."
        await notify_bot.send_message(notify_chat_id, text, protect_content=True)
        if media_path:
            path = Path(media_path)
            if path.exists():
                try:
                    if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                        await notify_bot.send_photo(
                            notify_chat_id, FSInputFile(path), protect_content=True
                        )
                    else:
                        await notify_bot.send_document(
                            notify_chat_id, FSInputFile(path), protect_content=True
                        )
                except Exception:
                    logger.warning("Failed sending story media %s", path, exc_info=True)

    return True
