from __future__ import annotations

import logging
from datetime import datetime

from apscheduler.triggers.interval import IntervalTrigger

from app.core.module_api import JobContext
from app.modules.automation.repository import AutomationRepository
from app.repositories.account_repo import AccountRepository
from app.telegram.client_utils import ensure_client_connected

logger = logging.getLogger(__name__)


async def _process_due(ctx: JobContext) -> None:
    now = datetime.now().astimezone()

    async with ctx.session_factory() as session:
        scheduled = await AutomationRepository(session).list_due_scheduled(now=now)
        reminders = await AutomationRepository(session).list_due_reminders(now=now)
        await session.commit()

    for item in scheduled:
        managed = ctx.pool.clients.get(item.account_id)
        if not managed:
            continue
        try:
            await ensure_client_connected(managed.client)
            await managed.client.send_message(item.peer_id, item.text)
            async with ctx.session_factory() as session:
                await AutomationRepository(session).mark_scheduled_sent(item.id)
                await session.commit()
        except Exception:
            logger.exception("Failed sending scheduled message id=%s", item.id)

    for reminder in reminders:
        async with ctx.session_factory() as session:
            account = await AccountRepository(session).get_by_id(reminder.account_id)
        if not account or not ctx.bot:
            continue
        chat_id = account.bot_chat_id or account.telegram_id
        await ctx.bot.send_message(
            chat_id,
            f"⏰ <b>یادآور</b>\n\n{reminder.text}",
            protect_content=True,
        )
        async with ctx.session_factory() as session:
            await AutomationRepository(session).mark_reminder_sent(reminder.id)
            await session.commit()


def register_jobs(ctx: JobContext) -> None:
    async def job() -> None:
        try:
            await _process_due(ctx)
        except Exception:
            logger.exception("Automation job failed")

    ctx.scheduler.add_job(
        job,
        trigger=IntervalTrigger(seconds=30),
        id="automation_due_messages",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
