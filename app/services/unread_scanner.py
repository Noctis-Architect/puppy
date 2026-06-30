"""Backward compatibility — use app.modules.archive.unread_scanner instead."""

from app.modules.archive.unread_scanner import scan_account_unread, scan_all_accounts

__all__ = ["scan_account_unread", "scan_all_accounts"]
