from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path

from apscheduler.triggers.interval import IntervalTrigger
from telethon.errors import RPCError
from telethon.tl.functions.stories import GetAllStoriesRequest, GetPeerStoriesRequest

from app.bot.concurrency import account_client_busy
from app.core.module_api import JobContext
from app.modules.contact_tracking.service import archive_story_item, capture_profile_snapshot
from app.modules.contact_tracking.utils import (
    extract_story_items,
    is_user_peer,
    peer_to_user_id,
    story_mentions_user,
)
from app.modules.settings.repository import AccountSettingsRepository, TrackedTargetRepository
from app.telegram.client_utils import ensure_client_connected

logger = logging.getLogger(__name__)

SCAN_INTERVAL_SECONDS = 300
STORY_INTERVAL_SECONDS = 600
MAX_STORIES_PER_RUN = 12
MAX_CONTACT_PEERS_PER_RUN = 40

_profile_scan_running: set[int] = set()
_story_scan_running: set[int] = set()
_profile_unresolved_notified: set[tuple[int, int]] = set()


async def _scan_profiles(ctx: JobContext) -> None:
    for account_id, managed in list(ctx.pool.clients.items()):
        if account_client_busy(account_id) or account_id in _profile_scan_running:
            continue

        _profile_scan_running.add(account_id)
        try:
            try:
                await ensure_client_connected(managed.client)
            except Exception:
                continue

            async with ctx.session_factory() as session:
                settings = await AccountSettingsRepository(session).get_or_create(account_id)
                if not settings.track_profile:
                    continue
                targets = await TrackedTargetRepository(session).list_for_account(account_id)

            notify_chat_id = managed.account.bot_chat_id or managed.account.telegram_id

            for target in targets:
                if account_client_busy(account_id):
                    break
                if not target.track_profile:
                    continue
                key = (account_id, target.target_user_id)
                try:
                    await capture_profile_snapshot(
                        client=managed.client,
                        session_factory=ctx.session_factory,
                        account_id=account_id,
                        target_user_id=target.target_user_id,
                        notify_bot=ctx.bot,
                        notify_chat_id=notify_chat_id,
                    )
                    _profile_unresolved_notified.discard(key)
                except RPCError as exc:
                    if ctx.bot and notify_chat_id:
                        await ctx.bot.send_message(
                            notify_chat_id,
                            f"⚠️ دسترسی به <code>{target.target_user_id}</code> قطع شد: {type(exc).__name__}",
                            protect_content=True,
                        )
                except Exception:
                    # Usually means Telethon still cannot resolve this user to an
                    # entity (no cached access hash) — see _add_target in
                    # group_tools/bot.py for the same failure mode. Tell the user
                    # once instead of failing forever in total silence.
                    logger.warning(
                        "Profile fetch failed account=%s target=%s",
                        account_id,
                        target.target_user_id,
                        exc_info=True,
                    )
                    if ctx.bot and notify_chat_id and key not in _profile_unresolved_notified:
                        _profile_unresolved_notified.add(key)
                        await ctx.bot.send_message(
                            notify_chat_id,
                            f"⚠️ ردیابی پروفایل <code>{target.target_user_id}</code> هنوز شروع "
                            "نشده — ربات هنوز نمی‌تونه پروفایلش رو پیدا کنه (نیاز به پیام "
                            "مشترک یا گروه مشترک داره). به‌محض ممکن‌شدن، خودکار فعال می‌شه.",
                            protect_content=True,
                        )
                await asyncio.sleep(0.3)
        finally:
            _profile_scan_running.discard(account_id)


async def _collect_story_sources(
    client,
    *,
    owner_user_id: int,
    tracked_ids: set[int],
    max_peers: int,
) -> list[tuple[int, object, str]]:
    pending: list[tuple[int, object, str]] = []
    seen: set[tuple[int, int]] = set()
    peers_seen = 0

    def _add(user_id: int | None, story, note: str = "") -> None:
        if user_id is None or len(pending) >= MAX_STORIES_PER_RUN:
            return
        story_id = getattr(story, "id", None)
        if not story_id:
            return
        key = (user_id, story_id)
        if key in seen:
            return
        seen.add(key)
        pending.append((user_id, story, note))

    try:
        result = await client(GetAllStoriesRequest())
        if getattr(result, "peer_stories", None):
            for peer_story in result.peer_stories:
                peers_seen += 1
                if peers_seen > max_peers:
                    break
                peer = getattr(peer_story, "peer", None)
                if not is_user_peer(peer):
                    continue
                user_id = peer_to_user_id(peer)
                for story in extract_story_items(peer_story):
                    note = " (تگ‌شده)" if story_mentions_user(story, owner_user_id) else ""
                    _add(user_id, story, note)
    except Exception:
        logger.warning("GetAllStories failed", exc_info=True)

    for user_id in tracked_ids:
        if len(pending) >= MAX_STORIES_PER_RUN:
            break
        try:
            peer = await client.get_input_entity(user_id)
            result = await client(GetPeerStoriesRequest(peer=peer))
            for story in extract_story_items(result):
                note = " (تگ‌شده)" if story_mentions_user(story, owner_user_id) else ""
                _add(user_id, story, note)
        except Exception:
            logger.debug("GetPeerStories failed target=%s", user_id, exc_info=True)

    return pending


async def _scan_stories(ctx: JobContext) -> None:
    media_dir = ctx.config.media_dir / "stories"
    media_dir.mkdir(parents=True, exist_ok=True)

    for account_id, managed in list(ctx.pool.clients.items()):
        if account_client_busy(account_id) or account_id in _story_scan_running:
            continue

        _story_scan_running.add(account_id)
        try:
            try:
                await ensure_client_connected(managed.client)
            except Exception:
                continue

            async with ctx.session_factory() as session:
                settings = await AccountSettingsRepository(session).get_or_create(account_id)
                if not settings.track_stories:
                    continue
                targets = await TrackedTargetRepository(session).list_for_account(account_id)

            tracked_ids = {t.target_user_id for t in targets if t.track_stories}
            owner_user_id = managed.account.telegram_id
            notify_chat_id = managed.account.bot_chat_id or owner_user_id

            story_sources = await _collect_story_sources(
                managed.client,
                owner_user_id=owner_user_id,
                tracked_ids=tracked_ids,
                max_peers=MAX_CONTACT_PEERS_PER_RUN,
            )

            for user_id, story, note in story_sources:
                if account_client_busy(account_id):
                    break
                try:
                    saved = await archive_story_item(
                        client=managed.client,
                        session_factory=ctx.session_factory,
                        account_id=account_id,
                        target_user_id=user_id,
                        story=story,
                        media_dir=media_dir,
                        download_media=True,
                        notify_bot=ctx.bot,
                        notify_chat_id=notify_chat_id,
                        mention_note=note,
                    )
                except Exception:
                    logger.warning(
                        "Story archive failed account=%s target=%s",
                        account_id,
                        user_id,
                        exc_info=True,
                    )
                    continue
                if saved:
                    await asyncio.sleep(0.2)
        finally:
            _story_scan_running.discard(account_id)


def register_jobs(ctx: JobContext) -> None:
    async def profile_job() -> None:
        try:
            asyncio.create_task(_scan_profiles(ctx))
        except Exception:
            logger.exception("Profile scan job failed")

    ctx.scheduler.add_job(
        profile_job,
        trigger=IntervalTrigger(seconds=SCAN_INTERVAL_SECONDS),
        id="contact_tracking_profile_scan",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now() + timedelta(minutes=2),
    )

    async def story_job() -> None:
        try:
            asyncio.create_task(_scan_stories(ctx))
        except Exception:
            logger.exception("Story scan job failed")

    ctx.scheduler.add_job(
        story_job,
        trigger=IntervalTrigger(seconds=STORY_INTERVAL_SECONDS),
        id="contact_tracking_story_scan",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now() + timedelta(minutes=5),
    )
