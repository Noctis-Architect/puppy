from __future__ import annotations

from datetime import datetime
from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.archive.models import StoredMessage
from app.modules.archive.repository import MessageRepository
from telethon import TelegramClient


class DeletionService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = MessageRepository(session)

    async def handle_deleted(
        self,
        *,
        account_id: int,
        chat_id: int | None,
        message_ids: list[int],
    ) -> list[StoredMessage]:
        return await self._repo.mark_deleted(
            account_id=account_id,
            chat_id=chat_id,
            message_ids=message_ids,
            deleted_at=datetime.now().astimezone(),
        )


class NotifierService:
    @staticmethod
    def _format_deleted_messages(*, messages: list[StoredMessage]) -> str:
        lines = ["🚨 پیام حذف شد", ""]
        for msg in messages:
            sender = msg.sender_name or "کاربر"
            received = msg.received_at.strftime("%H:%M") if msg.received_at else "-"
            lines.extend(
                [
                    f"👤 {sender}",
                    f"🆔 آیدی: <code>{msg.sender_id}</code>",
                    f"📝 {msg.text}",
                    f"🕐 {received}",
                    "—" * 20,
                ]
            )
        return "\n".join(lines)

    @staticmethod
    async def notify_deleted_messages(
        *,
        bot: Bot | None,
        bot_chat_id: int | None,
        owner_telegram_id: int,
        client: TelegramClient,
        messages: list[StoredMessage],
    ) -> None:
        if not messages:
            return

        text = NotifierService._format_deleted_messages(messages=messages)
        if bot and bot_chat_id:
            await bot.send_message(
                chat_id=bot_chat_id,
                text=text,
                protect_content=True,
            )
            for msg in messages:
                if not msg.media_path:
                    continue
                path = Path(msg.media_path)
                if not path.exists():
                    continue
                if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                    await bot.send_photo(
                        bot_chat_id,
                        FSInputFile(path),
                        protect_content=True,
                    )
                else:
                    await bot.send_document(
                        bot_chat_id,
                        FSInputFile(path),
                        protect_content=True,
                    )
            return

        await client.send_message("me", text)

    @staticmethod
    def format_edit_notification(*, message: StoredMessage, old_text: str) -> str:
        sender = message.sender_name or "کاربر"
        return (
            "✏️ پیام ویرایش شد\n\n"
            f"👤 {sender}\n"
            f"🆔 آیدی: <code>{message.sender_id}</code>\n"
            f"📝 قبل: {old_text}\n"
            f"📝 بعد: {message.text}"
        )

    @staticmethod
    async def notify_edited_message(
        *,
        bot: Bot | None,
        bot_chat_id: int | None,
        owner_telegram_id: int,
        client: TelegramClient,
        message: StoredMessage,
        old_text: str,
    ) -> None:
        text = NotifierService.format_edit_notification(message=message, old_text=old_text)
        if bot and bot_chat_id:
            await bot.send_message(chat_id=bot_chat_id, text=text, protect_content=True)
            return
        await client.send_message("me", text)
