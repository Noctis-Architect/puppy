from __future__ import annotations

import base64

import pytest

from app.services.anonymous_reveal.callback_decoder import (
    decode_callback_data,
    extract_user_id,
    extract_user_id_from_callback,
)


def test_decode_callback_data_utf8() -> None:
    assert decode_callback_data(b"block-7078242821") == "block-7078242821"


def test_decode_callback_data_from_export_base64() -> None:
    encoded = "YmxvY2stNzA3ODI0MjgyMQ"
    padded = encoded + "=" * (-len(encoded) % 4)
    raw = base64.b64decode(padded)
    assert decode_callback_data(raw) == "block-7078242821"


@pytest.mark.parametrize(
    ("decoded", "expected"),
    [
        ("block-7078242821", 7078242821),
        ("reply-123456", 123456),
        ("&&join", None),
        ("notif", None),
        ("block-1234", None),
    ],
)
def test_extract_user_id(decoded: str, expected: int | None) -> None:
    assert extract_user_id(decoded) == expected


def test_extract_user_id_from_callback() -> None:
    result = extract_user_id_from_callback(b"block-7078242821")
    assert result == ("block-7078242821", 7078242821)
