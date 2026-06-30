from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models import Account, Base


class AccountSettings(Base):
    __tablename__ = "account_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), unique=True, index=True
    )
    archive_media: Mapped[bool] = mapped_column(Boolean, default=True)
    track_edits: Mapped[bool] = mapped_column(Boolean, default=True)
    track_presence: Mapped[bool] = mapped_column(Boolean, default=True)
    track_profile: Mapped[bool] = mapped_column(Boolean, default=True)
    track_stories: Mapped[bool] = mapped_column(Boolean, default=False)
    typing_alerts: Mapped[bool] = mapped_column(Boolean, default=False)
    away_mode_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    away_message: Mapped[str | None] = mapped_column(Text)
    backup_own_messages: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_anon_reveal: Mapped[bool] = mapped_column(Boolean, default=True)
    group_mention_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    group_member_alerts: Mapped[bool] = mapped_column(Boolean, default=False)
    daily_summary: Mapped[bool] = mapped_column(Boolean, default=True)

    account: Mapped[Account] = relationship()


class TrackedTarget(Base):
    __tablename__ = "tracked_targets"
    __table_args__ = (
        UniqueConstraint("account_id", "target_user_id", name="uq_tracked_target"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    target_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    label: Mapped[str | None] = mapped_column(String(256))
    track_profile: Mapped[bool] = mapped_column(Boolean, default=True)
    track_presence: Mapped[bool] = mapped_column(Boolean, default=True)
    track_messages: Mapped[bool] = mapped_column(Boolean, default=True)
    track_stories: Mapped[bool] = mapped_column(Boolean, default=True)


class MonitoredChat(Base):
    __tablename__ = "monitored_chats"
    __table_args__ = (
        UniqueConstraint("account_id", "chat_id", name="uq_monitored_chat"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    title: Mapped[str | None] = mapped_column(String(256))
    save_deleted: Mapped[bool] = mapped_column(Boolean, default=True)
    save_edits: Mapped[bool] = mapped_column(Boolean, default=True)
