from __future__ import annotations

from app.db.models import Account
from app.repositories.account_repo import AccountRepository


async def get_own_account(repo: AccountRepository, user_id: int) -> Account | None:
    account = await repo.get_by_bot_chat_id(user_id)
    if account and account.bot_chat_id == user_id:
        return account
    account = await repo.get_by_telegram_id(user_id)
    if account and account.telegram_id == user_id:
        return account
    return None
