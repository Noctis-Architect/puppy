from __future__ import annotations

from telethon.tl.custom.message import Message


def extract_message_text(message: Message) -> str:
    if message.text:
        return message.text
    if message.message:
        return message.message
    if message.media:
        return f"[media: {type(message.media).__name__}]"
    return "[empty message]"


def format_sender_name(message: Message) -> str | None:
    sender = message.sender
    if sender is None:
        return None
    first = getattr(sender, "first_name", None) or ""
    last = getattr(sender, "last_name", None) or ""
    username = getattr(sender, "username", None)
    full = " ".join(part for part in (first, last) if part).strip()
    if username:
        return f"{full} (@{username})".strip() if full else f"@{username}"
    return full or None
