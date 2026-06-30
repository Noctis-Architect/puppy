from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.settings.models import AccountSettings, MonitoredChat, TrackedTarget


class AccountSettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create(self, account_id: int) -> AccountSettings:
        result = await self._session.execute(
            select(AccountSettings).where(AccountSettings.account_id == account_id)
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing
        settings = AccountSettings(account_id=account_id)
        self._session.add(settings)
        await self._session.flush()
        return settings

    async def toggle(self, account_id: int, field: str) -> AccountSettings:
        settings = await self.get_or_create(account_id)
        if hasattr(settings, field):
            setattr(settings, field, not getattr(settings, field))
        await self._session.flush()
        return settings


class TrackedTargetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        *,
        account_id: int,
        target_user_id: int,
        label: str | None = None,
    ) -> TrackedTarget:
        target = TrackedTarget(
            account_id=account_id,
            target_user_id=target_user_id,
            label=label,
        )
        self._session.add(target)
        await self._session.flush()
        return target

    async def remove(self, *, account_id: int, target_user_id: int) -> bool:
        result = await self._session.execute(
            delete(TrackedTarget).where(
                TrackedTarget.account_id == account_id,
                TrackedTarget.target_user_id == target_user_id,
            )
        )
        return (result.rowcount or 0) > 0

    async def list_for_account(self, account_id: int) -> list[TrackedTarget]:
        result = await self._session.execute(
            select(TrackedTarget)
            .where(TrackedTarget.account_id == account_id)
            .order_by(TrackedTarget.id)
        )
        return list(result.scalars().all())

    async def is_tracked(self, *, account_id: int, target_user_id: int) -> bool:
        result = await self._session.execute(
            select(TrackedTarget.id).where(
                TrackedTarget.account_id == account_id,
                TrackedTarget.target_user_id == target_user_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def list_all_targets(self) -> list[TrackedTarget]:
        result = await self._session.execute(select(TrackedTarget))
        return list(result.scalars().all())


class MonitoredChatRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        *,
        account_id: int,
        chat_id: int,
        title: str | None = None,
    ) -> MonitoredChat:
        chat = MonitoredChat(account_id=account_id, chat_id=chat_id, title=title)
        self._session.add(chat)
        await self._session.flush()
        return chat

    async def remove(self, *, account_id: int, chat_id: int) -> bool:
        result = await self._session.execute(
            delete(MonitoredChat).where(
                MonitoredChat.account_id == account_id,
                MonitoredChat.chat_id == chat_id,
            )
        )
        return (result.rowcount or 0) > 0

    async def list_for_account(self, account_id: int) -> list[MonitoredChat]:
        result = await self._session.execute(
            select(MonitoredChat)
            .where(MonitoredChat.account_id == account_id)
            .order_by(MonitoredChat.id)
        )
        return list(result.scalars().all())

    async def is_monitored(self, *, account_id: int, chat_id: int) -> bool:
        result = await self._session.execute(
            select(MonitoredChat.id).where(
                MonitoredChat.account_id == account_id,
                MonitoredChat.chat_id == chat_id,
                MonitoredChat.save_deleted.is_(True),
            )
        )
        return result.scalar_one_or_none() is not None

    async def list_monitored_chat_ids(self, account_id: int) -> set[int]:
        result = await self._session.execute(
            select(MonitoredChat.chat_id).where(
                MonitoredChat.account_id == account_id,
                MonitoredChat.save_deleted.is_(True),
            )
        )
        return {row[0] for row in result.all()}
