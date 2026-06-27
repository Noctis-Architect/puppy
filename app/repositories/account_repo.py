from __future__ import annotations

import secrets
import string

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Account

_REFERRAL_ALPHABET = string.ascii_uppercase + string.digits


def generate_referral_code(length: int = 6) -> str:
    return "".join(secrets.choice(_REFERRAL_ALPHABET) for _ in range(length))


class AccountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, account_id: int) -> Account | None:
        return await self._session.get(Account, account_id)

    async def get_by_telegram_id(self, telegram_id: int) -> Account | None:
        result = await self._session.execute(
            select(Account).where(Account.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def get_by_phone(self, phone: str) -> Account | None:
        result = await self._session.execute(select(Account).where(Account.phone == phone))
        return result.scalar_one_or_none()

    async def get_by_referral_code(self, code: str) -> Account | None:
        normalized = code.strip().upper()
        if not normalized:
            return None
        result = await self._session.execute(
            select(Account).where(Account.referral_code == normalized)
        )
        return result.scalar_one_or_none()

    async def get_by_bot_chat_id(self, bot_chat_id: int) -> Account | None:
        result = await self._session.execute(
            select(Account).where(Account.bot_chat_id == bot_chat_id)
        )
        return result.scalar_one_or_none()

    async def list_active(self) -> list[Account]:
        result = await self._session.execute(
            select(Account).where(Account.is_active.is_(True)).order_by(Account.id)
        )
        return list(result.scalars().all())

    async def _unique_referral_code(self) -> str:
        for _ in range(20):
            code = generate_referral_code()
            existing = await self.get_by_referral_code(code)
            if not existing:
                return code
        raise RuntimeError("Could not generate unique referral code")

    async def create(
        self,
        *,
        telegram_id: int,
        phone: str,
        session_path: str,
        username: str | None,
        display_name: str | None,
        bot_chat_id: int | None = None,
        referred_by: str | None = None,
    ) -> Account:
        referral_code = await self._unique_referral_code()
        account = Account(
            telegram_id=telegram_id,
            phone=phone,
            session_path=session_path,
            username=username,
            display_name=display_name,
            referral_code=referral_code,
            referred_by=referred_by.strip().upper() if referred_by else None,
            bot_chat_id=bot_chat_id,
            is_active=True,
        )
        self._session.add(account)
        await self._session.flush()
        return account

    async def set_active(self, account_id: int, active: bool) -> None:
        await self._session.execute(
            update(Account).where(Account.id == account_id).values(is_active=active)
        )

    async def delete(self, account_id: int) -> None:
        await self._session.execute(delete(Account).where(Account.id == account_id))
