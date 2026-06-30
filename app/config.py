from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.json"


@dataclass(frozen=True, slots=True)
class ProxyConfig:
    type: str
    host: str
    port: int
    username: str | None = None
    password: str | None = None
    secret: str | None = None


@dataclass(frozen=True, slots=True)
class CleanupConfig:
    hour: int = 3
    minute: int = 0
    timezone: str = "Asia/Tehran"
    retention_days: int = 90


@dataclass(frozen=True, slots=True)
class MonitoringConfig:
    unread_scan_interval_seconds: int = 60


@dataclass(frozen=True, slots=True)
class AppConfig:
    api_id: int
    api_hash: str
    bot_token: str
    super_admin_id: int
    database_url: str
    sessions_dir: Path
    media_dir: Path
    proxy: ProxyConfig | None
    cleanup: CleanupConfig
    monitoring: MonitoringConfig
    log_level: str

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> AppConfig:
        with path.open(encoding="utf-8") as f:
            raw: dict[str, Any] = json.load(f)

        proxy_raw = raw.get("proxy") or {}
        proxy: ProxyConfig | None = None
        if proxy_raw.get("type") and proxy_raw.get("host") and proxy_raw.get("port"):
            proxy = ProxyConfig(
                type=str(proxy_raw["type"]).lower(),
                host=str(proxy_raw["host"]),
                port=int(proxy_raw["port"]),
                username=proxy_raw.get("username"),
                password=proxy_raw.get("password"),
                secret=proxy_raw.get("secret"),
            )

        cleanup_raw = raw.get("cleanup") or {}
        cleanup = CleanupConfig(
            hour=int(cleanup_raw.get("hour", 3)),
            minute=int(cleanup_raw.get("minute", 0)),
            timezone=str(cleanup_raw.get("timezone", "Asia/Tehran")),
            retention_days=int(cleanup_raw.get("retention_days", 90)),
        )

        monitoring_raw = raw.get("monitoring") or {}
        monitoring = MonitoringConfig(
            unread_scan_interval_seconds=int(
                monitoring_raw.get("unread_scan_interval_seconds", 60)
            ),
        )

        db_url = str(raw.get("database_url", "sqlite+aiosqlite:///data/app.db"))
        if db_url.startswith("sqlite+aiosqlite:///") and not db_url.startswith("sqlite+aiosqlite:////"):
            rel = db_url.removeprefix("sqlite+aiosqlite:///")
            abs_path = (BASE_DIR / rel).resolve()
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            db_url = f"sqlite+aiosqlite:///{abs_path}"

        sessions_dir = BASE_DIR / str(raw.get("sessions_dir", "session"))
        sessions_dir.mkdir(parents=True, exist_ok=True)

        media_dir = BASE_DIR / str(raw.get("media_dir", "media"))
        media_dir.mkdir(parents=True, exist_ok=True)

        bot_token = str(raw.get("bot_token", "")).strip()
        if not bot_token:
            raise ValueError("bot_token is required in config.json")

        return cls(
            api_id=int(raw["api_id"]),
            api_hash=str(raw["api_hash"]),
            bot_token=bot_token,
            super_admin_id=int(raw.get("super_admin_id", 0)),
            database_url=db_url,
            sessions_dir=sessions_dir,
            media_dir=media_dir,
            proxy=proxy,
            cleanup=cleanup,
            monitoring=monitoring,
            log_level=str((raw.get("logging") or {}).get("level", "INFO")).upper(),
        )
