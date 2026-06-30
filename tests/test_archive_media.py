from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.archive.service import MediaArchiveService


@pytest.mark.asyncio
async def test_maybe_download_returns_none_without_media(tmp_path: Path) -> None:
    message = MagicMock()
    message.media = None
    client = AsyncMock()

    media_type, media_path = await MediaArchiveService.maybe_download(
        client=client,
        message=message,
        account_id=1,
        media_dir=tmp_path,
        archive_media=True,
    )

    assert media_type is None
    assert media_path is None
    client.download_media.assert_not_called()


@pytest.mark.asyncio
async def test_maybe_download_skips_when_archive_media_disabled(tmp_path: Path) -> None:
    message = MagicMock()
    message.media = MagicMock()
    message.ttl_period = None
    type(message.media).__name__ = "MessageMediaPhoto"
    client = AsyncMock()

    media_type, media_path = await MediaArchiveService.maybe_download(
        client=client,
        message=message,
        account_id=1,
        media_dir=tmp_path,
        archive_media=False,
    )

    assert media_type is None
    assert media_path is None
    client.download_media.assert_not_called()


@pytest.mark.asyncio
async def test_maybe_download_ephemeral_when_archive_media_disabled(tmp_path: Path) -> None:
    message = MagicMock()
    message.media = MagicMock()
    message.chat_id = 100
    message.id = 42
    message.ttl_period = 60
    type(message.media).__name__ = "MessageMediaPhoto"
    client = AsyncMock()
    client.download_media = AsyncMock(return_value=str(tmp_path / "file.jpg"))

    media_type, media_path = await MediaArchiveService.maybe_download(
        client=client,
        message=message,
        account_id=1,
        media_dir=tmp_path,
        archive_media=False,
    )

    assert media_type == "MessageMediaPhoto"
    assert media_path is not None
    client.download_media.assert_awaited_once()
