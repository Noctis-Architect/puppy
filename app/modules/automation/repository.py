from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.automation.models import Reminder, ScheduledMessage


class AutomationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_scheduled(
        self,
        *,
        account_id: int,
        peer_id: int,
        text: str,
        send_at: datetime,
    ) -> ScheduledMessage:
        msg = ScheduledMessage(
            account_id=account_id,
            peer_id=peer_id,
            text=text,
            send_at=send_at,
        )
        self._session.add(msg)
        await self._session.flush()
        return msg

    async def list_due_scheduled(self, *, now: datetime) -> list[ScheduledMessage]:
        result = await self._session.execute(
            select(ScheduledMessage).where(
                ScheduledMessage.sent.is_(False),
                ScheduledMessage.send_at <= now,
            )
        )
        return list(result.scalars().all())

    async def mark_scheduled_sent(self, msg_id: int) -> None:
        await self._session.execute(
            update(ScheduledMessage)
            .where(ScheduledMessage.id == msg_id)
            .values(sent=True)
        )

    async def add_reminder(
        self,
        *,
        account_id: int,
        text: str,
        remind_at: datetime,
    ) -> Reminder:
        reminder = Reminder(account_id=account_id, text=text, remind_at=remind_at)
        self._session.add(reminder)
        await self._session.flush()
        return reminder

    async def list_due_reminders(self, *, now: datetime) -> list[Reminder]:
        result = await self._session.execute(
            select(Reminder).where(
                Reminder.sent.is_(False),
                Reminder.remind_at <= now,
            )
        )
        return list(result.scalars().all())

    async def mark_reminder_sent(self, reminder_id: int) -> None:
        await self._session.execute(
            update(Reminder).where(Reminder.id == reminder_id).values(sent=True)
        )
