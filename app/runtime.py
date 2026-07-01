from __future__ import annotations

import asyncio
import logging
import signal

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.bot.service_context import ServiceContext
from app.bot.setup import create_bot, create_dispatcher, run_bot
from app.config import AppConfig
from app.core.loader import get_modules
from app.core.module_api import JobContext
from app.db.models import Account
from app.db.session import init_db
from app.logging_setup import setup_logging
from app.repositories.account_repo import AccountRepository
from app.telegram.pool import ClientPool, ManagedClient

logger = logging.getLogger(__name__)

_RECONNECT_INITIAL_DELAY = 5
_RECONNECT_MAX_DELAY = 300


async def run_service(config: AppConfig) -> None:
    setup_logging(config)
    session_factory = await init_db(config)
    bot = create_bot(config)
    pool = ClientPool(config=config, session_factory=session_factory, bot=bot)
    client_tasks: dict[int, asyncio.Task] = {}
    stop_event = asyncio.Event()

    async def _supervise_client(managed: ManagedClient) -> None:
        account_id = managed.account.id
        backoff = _RECONNECT_INITIAL_DELAY

        while not stop_event.is_set():
            try:
                await managed.client.run_until_disconnected()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Telethon client error for account id=%s", account_id)
            else:
                logger.warning(
                    "Telethon client disconnected for account id=%s",
                    account_id,
                )

            if stop_event.is_set():
                break

            if account_id in pool.clients:
                await pool.stop_account(account_id)

            logger.info(
                "Reconnecting account id=%s in %ss...",
                account_id,
                backoff,
            )
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=backoff)
                break
            except asyncio.TimeoutError:
                pass

            if stop_event.is_set():
                break

            try:
                async with session_factory() as session:
                    account = await AccountRepository(session).get_by_id(account_id)
                if account is None or not account.is_active:
                    logger.info(
                        "Account id=%s inactive or removed; stopping supervisor",
                        account_id,
                    )
                    break
                managed = await pool.start_account(account)
                backoff = _RECONNECT_INITIAL_DELAY
                logger.info("Reconnected monitoring for account id=%s", account_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "Reconnect failed for account id=%s; retrying",
                    account_id,
                )
                backoff = min(backoff * 2, _RECONNECT_MAX_DELAY)

        client_tasks.pop(account_id, None)
        if account_id in pool.clients:
            await pool.stop_account(account_id)

    def _spawn_client_task(managed: ManagedClient) -> asyncio.Task:
        task = asyncio.create_task(_supervise_client(managed))
        client_tasks[managed.account.id] = task
        return task

    async def on_new_account(account: Account) -> None:
        try:
            managed = await pool.start_account(account)
            _spawn_client_task(managed)
            logger.info("Live monitoring started for account id=%s", account.id)
        except Exception:
            logger.exception("Failed to start live monitoring for account id=%s", account.id)

    service_context = ServiceContext(pool=pool, on_new_account=on_new_account)
    dispatcher = create_dispatcher(
        config=config,
        session_factory=session_factory,
        service_context=service_context,
    )

    scheduler = AsyncIOScheduler(timezone=config.cleanup.timezone)
    job_ctx = JobContext(
        scheduler=scheduler,
        pool=pool,
        session_factory=session_factory,
        config=config,
        bot=bot,
    )
    job_modules = 0
    for module in get_modules():
        if module.register_jobs is not None:
            module.register_jobs(job_ctx)
            job_modules += 1
    scheduler.start()
    logger.info("Module schedulers started (%s job module(s))", job_modules)

    def _request_shutdown() -> None:
        logger.info("Shutdown requested...")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _request_shutdown)

    async def _run_bot() -> None:
        try:
            await run_bot(bot, dispatcher)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Bot polling stopped unexpectedly")

    bot_task = asyncio.create_task(_run_bot())

    try:
        await pool.start_all()
        if pool.clients:
            logger.info("Monitoring %s account(s).", len(pool.clients))
            for managed in pool.clients.values():
                _spawn_client_task(managed)
        else:
            logger.warning(
                "No active accounts yet. Bot is running for user registration."
            )

        await stop_event.wait()
    finally:
        stop_event.set()
        bot_task.cancel()
        for task in list(client_tasks.values()):
            task.cancel()
        await asyncio.gather(bot_task, *client_tasks.values(), return_exceptions=True)
        await dispatcher.stop_polling()
        await bot.session.close()
        scheduler.shutdown(wait=False)
        await pool.stop_all()
        logger.info("Service stopped.")
