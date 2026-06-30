"""Backward compatibility — use app.modules.archive.notifier and service."""

from app.modules.archive.notifier import DeletionService, NotifierService

__all__ = ["DeletionService", "NotifierService"]
