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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models import Account, Base


class StoredMessage(Base):
    __tablename__ = "stored_messages"
    __table_args__ = (
        UniqueConstraint("account_id", "chat_id", "message_id", name="uq_msg_per_account"),
        Index("ix_stored_messages_read_at", "read_at"),
        Index("ix_stored_messages_deleted_at", "deleted_at"),
        Index("ix_stored_messages_account_chat", "account_id", "chat_id"),
        Index("ix_stored_messages_account_msg", "account_id", "message_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    chat_id: Mapped[int] = mapped_column(BigInteger)
    sender_id: Mapped[int] = mapped_column(BigInteger)
    message_id: Mapped[int] = mapped_column(BigInteger)
    text: Mapped[str] = mapped_column(Text)
    sender_name: Mapped[str | None] = mapped_column(String(256))
    original_text: Mapped[str | None] = mapped_column(Text)
    edit_count: Mapped[int] = mapped_column(default=0)
    last_edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    media_type: Mapped[str | None] = mapped_column(String(64))
    media_path: Mapped[str | None] = mapped_column(String(512))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    account: Mapped[Account] = relationship(back_populates="messages")
