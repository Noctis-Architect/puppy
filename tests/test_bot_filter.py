from __future__ import annotations

from unittest.mock import MagicMock

from app.telegram.utils import is_bot_entity


def test_is_bot_entity_true() -> None:
    bot = MagicMock()
    bot.bot = True
    assert is_bot_entity(bot) is True


def test_is_bot_entity_false_for_users() -> None:
    user = MagicMock()
    user.bot = False
    assert is_bot_entity(user) is False


def test_is_bot_entity_none() -> None:
    assert is_bot_entity(None) is False
