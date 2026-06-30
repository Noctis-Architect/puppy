from __future__ import annotations

import logging
from datetime import datetime, timedelta

from apscheduler.triggers.cron import CronTrigger

from app.core.module_api import JobContext
from app.modules.archive.repository import MessageRepository
from app.modules.settings.repository import AccountSettingsRepository
from app.repositories.account_repo import AccountRepository

logger = logging.getLogger(__name__)


async def _send_daily_summary(ctx: JobContext) -> None:
    since = datetime.now().astimezone() - timedelta(days=1)

    async with ctx.session_factory() as session:
        accounts = await AccountRepository(session).list_active()

    for account in accounts:
        async with ctx.session_factory() as session:
            settings = await AccountSettingsRepository(session).get_or_create(account.id)
            if not settings.daily_summary:
                continue
            repo = MessageRepository(session)
            deleted = await repo.count_deleted_since(account_id=account.id, since=since)

        if deleted == 0:
            continue

        text = (
            "📊 <b>خلاصه روزانه</b>\n\n"
            f"🗑 پیام حذف‌شده: {deleted}\n"
            f"📅 بازه: ۲۴ ساعت گذشته"
        )
        if ctx.bot and account.bot_chat_id:
            await ctx.bot.send_message(account.bot_chat_id, text, protect_content=True)


def register_jobs(ctx: JobContext) -> None:
    async def job() -> None:
        try:
            await _send_daily_summary(ctx)
        except Exception:
            logger.exception("Daily summary job failed")

    ctx.scheduler.add_job(
        job,
        trigger=CronTrigger(
            hour=ctx.config.cleanup.hour,
            minute=max(0, ctx.config.cleanup.minute - 5),
            timezone=ctx.config.cleanup.timezone,
        ),
        id="memory_search_daily_summary",
        replace_existing=True,
        misfire_grace_time=3600,
    )
