from __future__ import annotations

import base64

from app.services.anonymous_reveal.bot_scanner import _extract_all_from_message, normalize_bot_username
from app.services.anonymous_reveal.callback_decoder import (
    callback_priority,
    decode_callback_data,
    extract_user_id,
    extract_user_id_from_callback,
    pick_best_callback,
)
from app.services.anonymous_reveal.usinfo_lookup import (
    _extract_inline_text,
    _parse_usinfo_response,
    _pick_inline_result,
    _response_matches_user,
)
from telethon.tl.types import BotInlineMessageText


def test_decode_callback_data_utf8() -> None:
    assert decode_callback_data(b"block-7078242821") == "block-7078242821"


def test_decode_callback_data_empty() -> None:
    assert decode_callback_data(b"") is None


def test_decode_callback_data_from_export_base64() -> None:
    encoded = "YmxvY2stNzA3ODI0MjgyMQ"
    padded = encoded + "=" * (-len(encoded) % 4)
    raw = base64.b64decode(padded)
    assert decode_callback_data(raw) == "block-7078242821"


def test_extract_user_id_cases() -> None:
    assert extract_user_id("block-7078242821") == 7078242821
    assert extract_user_id("reply-123456") == 123456
    assert extract_user_id("&&join") is None
    assert extract_user_id("notif") is None
    assert extract_user_id("block-1234") is None


def test_pick_best_callback_prefers_block() -> None:
    best = pick_best_callback(
        [
            ("reply-123456", 123456, "Reply"),
            ("block-7078242821", 7078242821, "Block"),
        ]
    )
    assert best == ("block-7078242821", 7078242821, "Block")


def test_callback_priority() -> None:
    assert callback_priority("block-1") < callback_priority("reply-1")


def test_normalize_bot_username() -> None:
    assert normalize_bot_username("@XBCHATBOT") == "xbchatbot"
    assert normalize_bot_username("  xbchatbot ") == "xbchatbot"


def test_parse_usinfo_phone() -> None:
    text = "ID: 7078242821\nUsername: @testuser\nName: Ali\n📱 +98 912 345 6789"
    parsed = _parse_usinfo_response(7078242821, text)
    assert parsed.phone == "+98 912 345 6789"


def test_parse_usinfo_response() -> None:
    text = "ID: 7078242821\nUsername: @testuser\nName: Ali Reza"
    parsed = _parse_usinfo_response(7078242821, text)
    assert parsed.username == "testuser"
    assert parsed.display_name == "Ali Reza"


def test_parse_usinfo_click_format() -> None:
    text = (
        "👤 \u20636790549285\n"
        "\u2063👦🏻 Aylin\n"
        "\u2063🌐@aylin_user\n"
        "🕑 Updated at 19/05/2026"
    )
    parsed = _parse_usinfo_response(6790549285, text)
    assert parsed.username == "aylin_user"
    assert parsed.display_name == "Aylin"


def test_parse_usinfo_markdown_link_format() -> None:
    text = (
        "👤 \u2063`8807668014`\n"
        "\u2063👦🏻 [Horal](tg://user?id=8807668014)\n"
        "\u2063🌐 @horalllll\n"
        "🕑 __Updated at 27/06/2026__"
    )
    parsed = _parse_usinfo_response(8807668014, text)
    assert parsed.username == "horalllll"
    assert parsed.display_name == "Horal"


def test_response_matches_user() -> None:
    assert _response_matches_user("ID: 7078242821\nUsername: @x", 7078242821)
    assert not _response_matches_user("Hello", 7078242821)


def test_response_matches_user_no_substring_false_positive() -> None:
    assert not _response_matches_user("ID: 1234567890\nUsername: @x", 123)


def test_extract_user_id_from_callback() -> None:
    result = extract_user_id_from_callback(b"block-7078242821")
    assert result == ("block-7078242821", 7078242821)


class _FakeInlineResult:
    def __init__(self, *, title: str = "", description: str = "", message=None) -> None:
        self.title = title
        self.description = description
        self.message = message


def test_extract_inline_text() -> None:
    msg = BotInlineMessageText(message="ID: 7078242821\nUsername: @abc")
    assert "7078242821" in _extract_inline_text(msg)


def test_pick_inline_result() -> None:
    results = [
        _FakeInlineResult(title="Other result"),
        _FakeInlineResult(
            title="Complete infos about 7078242821",
            message=BotInlineMessageText(message="ID: 7078242821"),
        ),
    ]
    picked = _pick_inline_result(results, 7078242821)
    assert picked is results[1]


class _FakeButton:
    def __init__(self, data: bytes, text: str = "") -> None:
        self.data = data
        self.text = text


class _FakeRow:
    def __init__(self, buttons) -> None:
        self.buttons = buttons


class _FakeMarkup:
    def __init__(self, rows) -> None:
        self.rows = rows


class _FakeMessage:
    def __init__(self, message_id: int, markup) -> None:
        self.id = message_id
        self.reply_markup = markup


def test_extract_all_from_message_collects_every_button() -> None:
    from telethon.tl.types import KeyboardButtonCallback, ReplyInlineMarkup

    markup = ReplyInlineMarkup(
        rows=[
            _FakeRow([KeyboardButtonCallback(text="Block", data=b"block-7078242821")]),
            _FakeRow([KeyboardButtonCallback(text="Reply", data=b"reply-123456789")]),
        ]
    )
    message = _FakeMessage(100, markup)
    found = _extract_all_from_message(message)
    assert len(found) == 2
    assert {item.user_id for item in found} == {7078242821, 123456789}
