from __future__ import annotations

import asyncio

# Limits concurrent Telethon auth flows so one burst cannot stall the bot.
AUTH_SEMAPHORE = asyncio.Semaphore(10)

_user_locks: dict[int, asyncio.Lock] = {}
_account_locks: dict[int, asyncio.Lock] = {}


def user_registration_lock(user_id: int) -> asyncio.Lock:
    lock = _user_locks.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        _user_locks[user_id] = lock
    return lock


def account_client_lock(account_id: int) -> asyncio.Lock:
    lock = _account_locks.get(account_id)
    if lock is None:
        lock = asyncio.Lock()
        _account_locks[account_id] = lock
    return lock
