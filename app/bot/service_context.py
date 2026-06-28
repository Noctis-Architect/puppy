from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.db.models import Account
from app.telegram.pool import ClientPool

OnNewAccountCallback = Callable[[Account], Awaitable[None]]


@dataclass(slots=True)
class ServiceContext:
    pool: ClientPool
    on_new_account: OnNewAccountCallback
