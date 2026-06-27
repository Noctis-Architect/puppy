from __future__ import annotations

import logging

from aiogram import Bot

from app.config import AppConfig
from app.db.models import Account

logger = logging.getLogger(__name__)


async def notify_super_admin_new_user(
    bot: Bot,
    config: AppConfig,
    account: Account,
) -> None:
    if not config.super_admin_id:
        return
    if account.telegram_id == config.super_admin_id:
        return

    username = f"@{account.username}" if account.username else "-"
    display_name = account.display_name or "-"
    lines = [
        "🆕 <b>کاربر جدید ثبت‌نام کرد</b>",
        "",
        f"🆔 آیدی: <code>{account.telegram_id}</code>",
        f"📱 شماره: <code>{account.phone}</code>",
        f"👤 یوزرنیم: {username}",
        f"📛 نام: {display_name}",
        f"🔢 account_id: {account.id}",
    ]
    if account.referred_by:
        lines.append(f"🎁 کد معرف: <code>{account.referred_by}</code>")

    try:
        await bot.send_message(chat_id=config.super_admin_id, text="\n".join(lines))
    except Exception:
        logger.exception(
            "Failed to notify super admin about new user account_id=%s",
            account.id,
        )
