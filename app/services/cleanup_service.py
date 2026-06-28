from __future__ import annotations

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import CleanupConfig
from app.repositories.message_repo import MessageRepository

logger = logging.getLogger(__name__)


class CleanupService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = MessageRepository(session)

    async def purge_yesterday_read_messages(self, config: CleanupConfig) -> int:
        tz = ZoneInfo(config.timezone)
        now = datetime.now(tz)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)
        retention_cutoff = now - timedelta(days=config.retention_days)

        read_deleted = await self._repo.delete_read_between(
            start=yesterday_start,
            end=today_start,
        )
        expired_deleted = await self._repo.delete_expired_deleted(before=retention_cutoff)
        total = read_deleted + expired_deleted
        logger.info(
            "Cleanup removed %s read non-deleted message(s) from %s, "
            "%s expired deleted message(s) older than %s days",
            read_deleted,
            yesterday_start.date(),
            expired_deleted,
            config.retention_days,
        )
        return total


async def run_daily_cleanup(
    factory: async_sessionmaker[AsyncSession],
    config: CleanupConfig,
) -> int:
    async with factory() as session:
        service = CleanupService(session)
        count = await service.purge_yesterday_read_messages(config)
        await session.commit()
        return count
