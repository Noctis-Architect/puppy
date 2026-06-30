from __future__ import annotations

from sqlalchemy import inspect, text


def light_migrations(sync_conn) -> None:
    inspector = inspect(sync_conn)
    if "account_settings" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("account_settings")}
    additions = {
        "archive_media": "BOOLEAN DEFAULT 1",
        "track_edits": "BOOLEAN DEFAULT 1",
        "track_presence": "BOOLEAN DEFAULT 1",
        "track_profile": "BOOLEAN DEFAULT 1",
        "track_stories": "BOOLEAN DEFAULT 0",
        "typing_alerts": "BOOLEAN DEFAULT 0",
        "away_mode_enabled": "BOOLEAN DEFAULT 0",
        "away_message": "TEXT",
        "backup_own_messages": "BOOLEAN DEFAULT 0",
        "auto_anon_reveal": "BOOLEAN DEFAULT 1",
        "group_mention_alerts": "BOOLEAN DEFAULT 1",
        "group_member_alerts": "BOOLEAN DEFAULT 0",
        "daily_summary": "BOOLEAN DEFAULT 1",
    }
    for name, ddl in additions.items():
        if name not in columns:
            sync_conn.execute(text(f"ALTER TABLE account_settings ADD COLUMN {name} {ddl}"))
