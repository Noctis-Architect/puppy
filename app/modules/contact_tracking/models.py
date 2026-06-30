from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base


class ProfileChange(Base):
    __tablename__ = "profile_changes"
    __table_args__ = (Index("ix_profile_changes_account_target", "account_id", "target_user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    target_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    field: Mapped[str] = mapped_column(String(32))
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PresenceEvent(Base):
    __tablename__ = "presence_events"
    __table_args__ = (Index("ix_presence_account_target", "account_id", "target_user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    target_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    status: Mapped[str] = mapped_column(String(32))
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ProfileSnapshot(Base):
    __tablename__ = "profile_snapshots"
    __table_args__ = (
        Index("ix_profile_snapshots_account_target", "account_id", "target_user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    target_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    display_name: Mapped[str | None] = mapped_column(String(256))
    username: Mapped[str | None] = mapped_column(String(64))
    bio: Mapped[str | None] = mapped_column(Text)
    photo_id: Mapped[str | None] = mapped_column(String(128))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class StoryArchive(Base):
    __tablename__ = "story_archives"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    target_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    story_id: Mapped[int] = mapped_column(BigInteger)
    media_path: Mapped[str | None] = mapped_column(String(512))
    saved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
