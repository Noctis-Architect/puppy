from __future__ import annotations

from telethon.tl.types import MessageEntityMentionName, PeerChannel, PeerUser


def extract_photo_id(entity) -> str | None:
    photo = getattr(entity, "photo", None)
    if photo is None:
        return None
    photo_id = getattr(photo, "photo_id", None)
    return str(photo_id) if photo_id else None


def peer_to_user_id(peer) -> int | None:
    if isinstance(peer, PeerUser):
        return peer.user_id
    return None


def extract_story_items(result) -> list:
    """Normalize PeerStories / GetPeerStories responses to StoryItem list."""
    stories = getattr(result, "stories", None)
    if stories is None:
        return []
    if isinstance(stories, list):
        return stories
    nested = getattr(stories, "stories", None)
    return nested if isinstance(nested, list) else []


def story_mentions_user(story, user_id: int) -> bool:
    for entity in getattr(story, "entities", None) or []:
        if isinstance(entity, MessageEntityMentionName) and entity.user_id == user_id:
            return True
    caption_entities = getattr(story, "caption_entities", None)
    for entity in caption_entities or []:
        if isinstance(entity, MessageEntityMentionName) and entity.user_id == user_id:
            return True
    return False


def is_user_peer(peer) -> bool:
    return isinstance(peer, PeerUser)


def is_channel_peer(peer) -> bool:
    return isinstance(peer, PeerChannel)
