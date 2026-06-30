from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.contact_tracking.models import PresenceEvent, ProfileChange, ProfileSnapshot, StoryArchive


class ContactTrackingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_snapshot(
        self, *, account_id: int, target_user_id: int
    ) -> ProfileSnapshot | None:
        result = await self._session.execute(
            select(ProfileSnapshot).where(
                ProfileSnapshot.account_id == account_id,
                ProfileSnapshot.target_user_id == target_user_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_snapshot(
        self,
        *,
        account_id: int,
        target_user_id: int,
        display_name: str | None,
        username: str | None,
        bio: str | None,
        photo_id: str | None,
    ) -> ProfileSnapshot:
        snap = await self.get_snapshot(
            account_id=account_id, target_user_id=target_user_id
        )
        if snap is None:
            snap = ProfileSnapshot(
                account_id=account_id,
                target_user_id=target_user_id,
            )
            self._session.add(snap)
        snap.display_name = display_name
        snap.username = username
        snap.bio = bio
        snap.photo_id = photo_id
        snap.updated_at = datetime.now().astimezone()
        await self._session.flush()
        return snap

    async def add_profile_change(
        self,
        *,
        account_id: int,
        target_user_id: int,
        field: str,
        old_value: str | None,
        new_value: str | None,
    ) -> ProfileChange:
        change = ProfileChange(
            account_id=account_id,
            target_user_id=target_user_id,
            field=field,
            old_value=old_value,
            new_value=new_value,
        )
        self._session.add(change)
        await self._session.flush()
        return change

    async def list_profile_changes(
        self, *, account_id: int, target_user_id: int, limit: int = 20
    ) -> list[ProfileChange]:
        result = await self._session.execute(
            select(ProfileChange)
            .where(
                ProfileChange.account_id == account_id,
                ProfileChange.target_user_id == target_user_id,
            )
            .order_by(ProfileChange.changed_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def add_presence(
        self, *, account_id: int, target_user_id: int, status: str
    ) -> PresenceEvent:
        event = PresenceEvent(
            account_id=account_id,
            target_user_id=target_user_id,
            status=status,
        )
        self._session.add(event)
        await self._session.flush()
        return event

    async def list_presence(
        self, *, account_id: int, target_user_id: int, limit: int = 20
    ) -> list[PresenceEvent]:
        result = await self._session.execute(
            select(PresenceEvent)
            .where(
                PresenceEvent.account_id == account_id,
                PresenceEvent.target_user_id == target_user_id,
            )
            .order_by(PresenceEvent.at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def has_story_archived(
        self, *, account_id: int, target_user_id: int, story_id: int
    ) -> bool:
        result = await self._session.execute(
            select(StoryArchive.id).where(
                StoryArchive.account_id == account_id,
                StoryArchive.target_user_id == target_user_id,
                StoryArchive.story_id == story_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def add_story_archive(
        self,
        *,
        account_id: int,
        target_user_id: int,
        story_id: int,
        media_path: str | None,
    ) -> StoryArchive:
        story = StoryArchive(
            account_id=account_id,
            target_user_id=target_user_id,
            story_id=story_id,
            media_path=media_path,
        )
        self._session.add(story)
        await self._session.flush()
        return story

    async def list_stories(
        self, *, account_id: int, target_user_id: int, limit: int = 10
    ) -> list[StoryArchive]:
        result = await self._session.execute(
            select(StoryArchive)
            .where(
                StoryArchive.account_id == account_id,
                StoryArchive.target_user_id == target_user_id,
            )
            .order_by(StoryArchive.saved_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
