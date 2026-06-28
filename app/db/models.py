from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(32), unique=True)
    session_path: Mapped[str] = mapped_column(String(512), unique=True)
    username: Mapped[str | None] = mapped_column(String(64), index=True)
    display_name: Mapped[str | None] = mapped_column(String(256))
    referral_code: Mapped[str | None] = mapped_column(String(16), unique=True, index=True)
    referred_by: Mapped[str | None] = mapped_column(String(16), index=True)
    bot_chat_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    messages: Mapped[list[StoredMessage]] = relationship(back_populates="account")


class StoredMessage(Base):
    __tablename__ = "stored_messages"
    __table_args__ = (
        UniqueConstraint("account_id", "chat_id", "message_id", name="uq_msg_per_account"),
        Index("ix_stored_messages_read_at", "read_at"),
        Index("ix_stored_messages_deleted_at", "deleted_at"),
        Index("ix_stored_messages_account_chat", "account_id", "chat_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    chat_id: Mapped[int] = mapped_column(BigInteger)
    sender_id: Mapped[int] = mapped_column(BigInteger)
    message_id: Mapped[int] = mapped_column(BigInteger)
    text: Mapped[str] = mapped_column(Text)
    sender_name: Mapped[str | None] = mapped_column(String(256))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    account: Mapped[Account] = relationship(back_populates="messages")
