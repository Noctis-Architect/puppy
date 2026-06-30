"""Backward compatibility — use app.modules.archive.service instead."""

from app.modules.archive.service import MessageService, with_message_service

__all__ = ["MessageService", "with_message_service"]
