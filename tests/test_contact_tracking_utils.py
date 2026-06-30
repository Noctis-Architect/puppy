from __future__ import annotations

from unittest.mock import MagicMock

from telethon.tl.types import MessageEntityMentionName, PeerUser

from app.modules.contact_tracking.utils import (
    extract_photo_id,
    extract_story_items,
    peer_to_user_id,
    story_mentions_user,
)


def test_extract_story_items_from_list() -> None:
    story = MagicMock()
    result = MagicMock()
    result.stories = [story]
    assert extract_story_items(result) == [story]


def test_extract_story_items_from_nested_object() -> None:
    story = MagicMock()
    nested = MagicMock()
    nested.stories = [story]
    result = MagicMock()
    result.stories = nested
    assert extract_story_items(result) == [story]


def test_extract_story_items_empty() -> None:
    result = MagicMock()
    result.stories = None
    assert extract_story_items(result) == []


def test_peer_to_user_id() -> None:
    assert peer_to_user_id(PeerUser(user_id=123)) == 123
    assert peer_to_user_id(MagicMock()) is None


def test_extract_photo_id_none_when_missing() -> None:
    entity = MagicMock()
    entity.photo = None
    assert extract_photo_id(entity) is None


def test_extract_photo_id_from_photo() -> None:
    entity = MagicMock()
    entity.photo.photo_id = 999
    assert extract_photo_id(entity) == "999"


def test_story_mentions_user() -> None:
    story = MagicMock()
    story.entities = [MessageEntityMentionName(offset=0, length=1, user_id=42)]
    story.caption_entities = None
    assert story_mentions_user(story, 42) is True
    assert story_mentions_user(story, 99) is False
