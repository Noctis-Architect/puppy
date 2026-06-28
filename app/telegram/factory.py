from __future__ import annotations

import asyncio
import logging
from typing import Any

from telethon import TelegramClient

from app.config import AppConfig
from app.telegram.proxy import (
    FALLBACK_PROXIES,
    client_kwargs_for_proxy,
    proxy_label,
    proxy_to_tuple,
)

logger = logging.getLogger(__name__)


def _cleanup_broken_session(session_path: str) -> None:
    from pathlib import Path

    for suffix in (".session", ".session-journal"):
        path = Path(f"{session_path}{suffix}")
        if path.exists():
            path.unlink()


async def _safe_disconnect(client: TelegramClient, session_path: str) -> None:
    try:
        await client.disconnect()
    except Exception as exc:
        logger.debug("Disconnect failed for %s: %s", session_path, exc)
        _cleanup_broken_session(session_path)


async def _try_connect(client: TelegramClient, session_path: str, retries: int = 3) -> bool:
    for attempt in range(1, retries + 1):
        try:
            await client.connect()
            return True
        except (TimeoutError, OSError, ConnectionError, asyncio.IncompleteReadError) as exc:
            logger.debug("Connect attempt %s failed: %s", attempt, exc)
            await _safe_disconnect(client, session_path)
            if attempt < retries:
                await asyncio.sleep(2)
    return False


def _connection_candidates(config: AppConfig) -> list[tuple[Any, ...] | None]:
    candidates: list[tuple[Any, ...] | None] = []
    seen: set[tuple[Any, ...]] = set()

    if config.proxy:
        configured = proxy_to_tuple(config.proxy)
        candidates.append(configured)
        seen.add(configured)

    candidates.append(None)

    for proxy in FALLBACK_PROXIES:
        if proxy not in seen:
            candidates.append(proxy)
            seen.add(proxy)

    return candidates


async def connect_client(
    config: AppConfig,
    session_path: str,
) -> TelegramClient:
    errors: list[str] = []

    for proxy in _connection_candidates(config):
        label = proxy_label(proxy)
        logger.info("Trying Telegram connection via %s...", label)
        client = TelegramClient(
            session_path,
            config.api_id,
            config.api_hash,
            **client_kwargs_for_proxy(proxy),
        )
        if await _try_connect(client, session_path):
            logger.info("Connected via %s", label)
            return client
        await _safe_disconnect(client, session_path)
        errors.append(label)

    raise ConnectionError(
        "Could not connect to Telegram. Tried: "
        + ", ".join(errors)
        + ". Check network/proxy settings in config.json."
    )
