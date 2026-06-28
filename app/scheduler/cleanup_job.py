from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import CleanupConfig
from app.services.cleanup_service import run_daily_cleanup

logger = logging.getLogger(__name__)


def setup_cleanup_scheduler(
    factory: async_sessionmaker[AsyncSession],
    config: CleanupConfig,
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=config.timezone)

    async def job() -> None:
        try:
            count = await run_daily_cleanup(factory, config)
            logger.info("Daily cleanup finished, deleted=%s", count)
        except Exception:
            logger.exception("Daily cleanup failed")

    scheduler.add_job(
        job,
        trigger=CronTrigger(
            hour=config.hour,
            minute=config.minute,
            timezone=config.timezone,
        ),
        id="purge_yesterday_read_messages",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    return scheduler
