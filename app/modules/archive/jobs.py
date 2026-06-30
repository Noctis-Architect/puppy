from __future__ import annotations

import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.core.module_api import JobContext
from app.modules.archive.cleanup import run_daily_cleanup
from app.modules.archive.unread_scanner import scan_all_accounts

logger = logging.getLogger(__name__)


def register_jobs(ctx: JobContext) -> None:
    scheduler = ctx.scheduler

    async def cleanup_job() -> None:
        try:
            count = await run_daily_cleanup(ctx.session_factory, ctx.config.cleanup)
            logger.info("Daily cleanup finished, deleted=%s", count)
        except Exception:
            logger.exception("Daily cleanup failed")

    scheduler.add_job(
        cleanup_job,
        trigger=CronTrigger(
            hour=ctx.config.cleanup.hour,
            minute=ctx.config.cleanup.minute,
            timezone=ctx.config.cleanup.timezone,
        ),
        id="archive_daily_cleanup",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    async def unread_job() -> None:
        try:
            asyncio.create_task(
                scan_all_accounts(ctx.pool, ctx.session_factory, media_dir=ctx.config.media_dir)
            )
        except Exception:
            logger.exception("Unread scan job failed")

    scheduler.add_job(
        unread_job,
        trigger=IntervalTrigger(seconds=ctx.config.monitoring.unread_scan_interval_seconds),
        id="archive_unread_scan",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(),
    )
