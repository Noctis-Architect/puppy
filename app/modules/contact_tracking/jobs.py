from __future__ import annotations

import asyncio
import logging

from apscheduler.triggers.interval import IntervalTrigger

from app.core.module_api import JobContext
from app.modules.contact_tracking.repository import ContactTrackingRepository
from app.modules.settings.repository import AccountSettingsRepository, TrackedTargetRepository
from app.telegram.client_utils import ensure_client_connected

logger = logging.getLogger(__name__)

SCAN_INTERVAL_SECONDS = 300


async def _scan_profiles(ctx: JobContext) -> None:
    for account_id, managed in list(ctx.pool.clients.items()):
        try:
            await ensure_client_connected(managed.client)
        except Exception:
            continue

        async with ctx.session_factory() as session:
            settings = await AccountSettingsRepository(session).get_or_create(account_id)
            if not settings.track_profile:
                continue
            targets = await TrackedTargetRepository(session).list_for_account(account_id)

        for target in targets:
            if not target.track_profile:
                continue
            try:
                entity = await managed.client.get_entity(target.target_user_id)
            except Exception as exc:
                if ctx.bot and managed.account.bot_chat_id:
                    await ctx.bot.send_message(
                        managed.account.bot_chat_id or managed.account.telegram_id,
                        f"⚠️ دسترسی به <code>{target.target_user_id}</code> قطع شد: {type(exc).__name__}",
                        protect_content=True,
                    )
                continue

            display_name = " ".join(
                p for p in (getattr(entity, "first_name", ""), getattr(entity, "last_name", "")) if p
            ).strip() or None
            username = getattr(entity, "username", None)
            bio = getattr(entity, "about", None) or getattr(entity, "bio", None)
            photo_id = None
            if getattr(entity, "photo", None):
                photo_id = str(getattr(entity.photo, "photo_id", ""))

            async with ctx.session_factory() as session:
                repo = ContactTrackingRepository(session)
                old = await repo.get_snapshot(
                    account_id=account_id, target_user_id=target.target_user_id
                )
                snap = await repo.upsert_snapshot(
                    account_id=account_id,
                    target_user_id=target.target_user_id,
                    display_name=display_name,
                    username=username,
                    bio=bio,
                    photo_id=photo_id,
                )
                changes: list[tuple[str, str | None, str | None]] = []
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
                                target_user_id=target.target_user_id,
                                field=field,
                                old_value=old_v,
                                new_value=new_v,
                            )
                await session.commit()

            if changes and ctx.bot:
                chat_id = managed.account.bot_chat_id or managed.account.telegram_id
                lines = [f"👤 تغییر پروفایل <code>{target.target_user_id}</code>", ""]
                for field, old_v, new_v in changes:
                    lines.append(f"• {field}: {old_v or '-'} → {new_v or '-'}")
                await ctx.bot.send_message(chat_id, "\n".join(lines), protect_content=True)

            await asyncio.sleep(0.5)


def register_jobs(ctx: JobContext) -> None:
    async def job() -> None:
        try:
            await _scan_profiles(ctx)
        except Exception:
            logger.exception("Profile scan job failed")

    ctx.scheduler.add_job(
        job,
        trigger=IntervalTrigger(seconds=SCAN_INTERVAL_SECONDS),
        id="contact_tracking_profile_scan",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
