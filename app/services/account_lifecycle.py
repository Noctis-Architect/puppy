from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import AppConfig
from app.repositories.account_repo import AccountRepository
from app.telegram.pool import ClientPool

logger = logging.getLogger(__name__)


def delete_session_files(session_path: str) -> None:
    base = Path(session_path)
    for suffix in (".session", ".session-journal"):
        path = Path(f"{base}{suffix}")
        if path.exists():
            path.unlink()


async def delete_account(
    config: AppConfig,
    db: AsyncSession,
    account_id: int,
    *,
    pool: ClientPool | None = None,
) -> bool:
    repo = AccountRepository(db)
    account = await repo.get_by_id(account_id)
    if not account:
        return False

    if pool is not None:
        await pool.stop_account(account_id)

    delete_session_files(account.session_path)
    pending = config.sessions_dir / f"_pending_bot_{account.bot_chat_id or account.telegram_id}"
    delete_session_files(str(pending))

    await repo.delete(account_id)
    await db.commit()
    logger.info(
        "Deleted account id=%s telegram_id=%s",
        account_id,
        account.telegram_id,
    )
    return True
