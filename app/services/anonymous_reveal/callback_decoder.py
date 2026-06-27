from __future__ import annotations

import base64
import binascii
import re

USER_ID_PATTERN = re.compile(r"^[a-zA-Z&_]+-(\d{5,})$")
PREFERRED_CALLBACK_PREFIXES = ("block", "report", "ban", "reply", "user")


def decode_callback_data(data: bytes) -> str | None:
    if not data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        pass

    padded = data + b"=" * (-len(data) % 4)
    try:
        return base64.b64decode(padded).decode("utf-8", errors="replace")
    except (binascii.Error, ValueError):
        return None


def extract_user_id(decoded: str) -> int | None:
    match = USER_ID_PATTERN.match(decoded.strip())
    if not match:
        return None
    return int(match.group(1))


def callback_priority(decoded: str) -> int:
    prefix = decoded.split("-", 1)[0].lower()
    for index, preferred in enumerate(PREFERRED_CALLBACK_PREFIXES):
        if prefix == preferred:
            return index
    return len(PREFERRED_CALLBACK_PREFIXES)


def extract_user_id_from_callback(data: bytes) -> tuple[str, int] | None:
    decoded = decode_callback_data(data)
    if decoded is None:
        return None
    user_id = extract_user_id(decoded)
    if user_id is None:
        return None
    return decoded, user_id


def pick_best_callback(
    candidates: list[tuple[str, int, str]],
) -> tuple[str, int, str] | None:
    if not candidates:
        return None
    return min(candidates, key=lambda item: (callback_priority(item[0]), item[0]))
