from __future__ import annotations

import asyncio
import logging
import signal

from app.bot.service_context import ServiceContext
from app.bot.setup import create_bot, create_dispatcher, run_bot
from app.config import AppConfig
from app.db.models import Account
from app.db.session import init_db
from app.logging_setup import setup_logging
from app.scheduler.cleanup_job import setup_cleanup_scheduler
from app.scheduler.unread_scan_job import setup_unread_scan_scheduler
from app.services.unread_scanner import scan_account_unread, scan_all_accounts
from app.telegram.pool import ClientPool

logger = logging.getLogger(__name__)


async def run_service(config: AppConfig) -> None:
    setup_logging(config)
    session_factory = await init_db(config)
    bot = create_bot(config)
    pool = ClientPool(config=config, session_factory=session_factory, bot=bot)
    account_tasks: list[asyncio.Task] = []

    async def on_new_account(account: Account) -> None:
        try:
            managed = await pool.start_account(account)
            task = asyncio.create_task(managed.client.run_until_disconnected())
            account_tasks.append(task)
            asyncio.create_task(
                scan_account_unread(
                    managed.client,
                    account_id=account.id,
                    session_factory=session_factory,
                )
            )
            logger.info("Live monitoring started for account id=%s", account.id)
        except Exception:
            logger.exception("Failed to start live monitoring for account id=%s", account.id)

    service_context = ServiceContext(pool=pool, on_new_account=on_new_account)
    dispatcher = create_dispatcher(
        config=config,
        session_factory=session_factory,
        service_context=service_context,
    )
    scheduler = setup_cleanup_scheduler(session_factory, config.cleanup)
    scheduler.start()
    logger.info(
        "Cleanup scheduled daily at %02d:%02d (%s), retention=%s days",
        config.cleanup.hour,
        config.cleanup.minute,
        config.cleanup.timezone,
        config.cleanup.retention_days,
    )

    unread_scheduler = setup_unread_scan_scheduler(pool, session_factory, config.monitoring)
    unread_scheduler.start()
    logger.info(
        "Unread scan scheduled every %s seconds",
        config.monitoring.unread_scan_interval_seconds,
    )

    stop_event = asyncio.Event()

    def _request_shutdown() -> None:
        logger.info("Shutdown requested...")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _request_shutdown)

    bot_task = asyncio.create_task(run_bot(bot, dispatcher))
    run_tasks: list[asyncio.Task] = [bot_task]

    try:
        await pool.start_all()
        if pool.clients:
            logger.info("Monitoring %s account(s).", len(pool.clients))
            asyncio.create_task(scan_all_accounts(pool, session_factory))
            run_tasks.extend(
                asyncio.create_task(managed.client.run_until_disconnected())
                for managed in pool.clients.values()
            )
        else:
            logger.warning(
                "No active accounts yet. Bot is running for user registration."
            )

        stop_task = asyncio.create_task(stop_event.wait())
        done, pending = await asyncio.wait(
            run_tasks + account_tasks + [stop_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in run_tasks + account_tasks:
            if task not in done:
                task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
    finally:
        await dispatcher.stop_polling()
        await bot.session.close()
        unread_scheduler.shutdown(wait=False)
        scheduler.shutdown(wait=False)
        await pool.stop_all()
        logger.info("Service stopped.")
