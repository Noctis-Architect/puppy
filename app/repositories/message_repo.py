"""Backward compatibility — use app.modules.archive.repository instead."""

from app.modules.archive.repository import MessageRepository

__all__ = ["MessageRepository"]
