from __future__ import annotations

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import CleanupConfig
from app.modules.archive.repository import MessageRepository

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
        media_cutoff = now - timedelta(days=config.retention_days)
        expired_media = await self._repo.delete_expired_media(before=media_cutoff)
        total = read_deleted + expired_deleted + expired_media
        logger.info(
            "Cleanup removed %s read, %s expired deleted, %s expired media",
            read_deleted,
            expired_deleted,
            expired_media,
        )
        return total


async def run_daily_cleanup(factory, config: CleanupConfig) -> int:
    async with factory() as session:
        service = CleanupService(session)
        count = await service.purge_yesterday_read_messages(config)
        await session.commit()
        return count
