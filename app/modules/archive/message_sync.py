from __future__ import annotations

import asyncio

_locks: dict[tuple[int, int], asyncio.Lock] = {}


def message_lock(account_id: int, message_id: int) -> asyncio.Lock:
    """Per-message lock so deletion handlers wait for in-flight store tasks."""
    key = (account_id, message_id)
    lock = _locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _locks[key] = lock
    return lock


async def wait_for_store(account_id: int, message_id: int) -> None:
    async with message_lock(account_id, message_id):
        return
