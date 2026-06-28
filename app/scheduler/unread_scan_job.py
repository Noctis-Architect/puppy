from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import MonitoringConfig
from app.services.unread_scanner import scan_all_accounts
from app.telegram.pool import ClientPool

logger = logging.getLogger(__name__)


def setup_unread_scan_scheduler(
    pool: ClientPool,
    factory: async_sessionmaker[AsyncSession],
    config: MonitoringConfig,
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()

    async def job() -> None:
        try:
            await scan_all_accounts(pool, factory)
        except Exception:
            logger.exception("Unread scan job failed")

    scheduler.add_job(
        job,
        trigger=IntervalTrigger(seconds=config.unread_scan_interval_seconds),
        id="scan_unread_private_messages",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    return scheduler
