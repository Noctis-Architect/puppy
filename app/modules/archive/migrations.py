from __future__ import annotations

from sqlalchemy import inspect, text


def light_migrations(sync_conn) -> None:
    inspector = inspect(sync_conn)
    if "accounts" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("accounts")}
    if "username" not in columns:
        sync_conn.execute(text("ALTER TABLE accounts ADD COLUMN username VARCHAR(64)"))
    if "referral_code" not in columns:
        sync_conn.execute(text("ALTER TABLE accounts ADD COLUMN referral_code VARCHAR(16)"))
    if "referred_by" not in columns:
        sync_conn.execute(text("ALTER TABLE accounts ADD COLUMN referred_by VARCHAR(16)"))
    if "bot_chat_id" not in columns:
        sync_conn.execute(text("ALTER TABLE accounts ADD COLUMN bot_chat_id BIGINT"))

    if "stored_messages" not in inspector.get_table_names():
        return

    msg_columns = {col["name"] for col in inspector.get_columns("stored_messages")}
    indexes = {idx["name"] for idx in inspector.get_indexes("stored_messages")}

    if "deleted_at" not in msg_columns:
        sync_conn.execute(text("ALTER TABLE stored_messages ADD COLUMN deleted_at DATETIME"))
    if "original_text" not in msg_columns:
        sync_conn.execute(text("ALTER TABLE stored_messages ADD COLUMN original_text TEXT"))
    if "edit_count" not in msg_columns:
        sync_conn.execute(
            text("ALTER TABLE stored_messages ADD COLUMN edit_count INTEGER DEFAULT 0")
        )
    if "last_edited_at" not in msg_columns:
        sync_conn.execute(
            text("ALTER TABLE stored_messages ADD COLUMN last_edited_at DATETIME")
        )
    if "media_type" not in msg_columns:
        sync_conn.execute(text("ALTER TABLE stored_messages ADD COLUMN media_type VARCHAR(64)"))
    if "media_path" not in msg_columns:
        sync_conn.execute(text("ALTER TABLE stored_messages ADD COLUMN media_path VARCHAR(512)"))
    if "ix_stored_messages_deleted_at" not in indexes:
        sync_conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_stored_messages_deleted_at "
                "ON stored_messages (deleted_at)"
            )
        )
    if "ix_stored_messages_account_msg" not in indexes:
        sync_conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_stored_messages_account_msg "
                "ON stored_messages (account_id, message_id)"
            )
        )
