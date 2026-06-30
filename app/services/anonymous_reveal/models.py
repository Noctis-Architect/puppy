from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ScanResult:
    message_id: int
    button_text: str
    decoded_callback: str
    user_id: int


@dataclass(slots=True)
class UserLookup:
    user_id: int
    username: str | None
    display_name: str | None
    phone: str | None
    raw_response: str


@dataclass(slots=True)
class RevealResult:
    bot_username: str
    message_id: int
    button_text: str
    decoded_callback: str
    user_id: int
    username: str | None
    display_name: str | None
    phone: str | None = None
    lookup_failed: bool = False


@dataclass(slots=True)
class RevealBatchResult:
    bot_username: str
    entries: list[RevealResult]
    messages_scanned: int
    buttons_found: int
    scan_limited: bool = False
