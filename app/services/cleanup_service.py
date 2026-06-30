"""Backward compatibility — use app.modules.archive.cleanup instead."""

from app.modules.archive.cleanup import CleanupService, run_daily_cleanup

__all__ = ["CleanupService", "run_daily_cleanup"]
