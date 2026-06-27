from __future__ import annotations

from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.access import get_own_account
from app.bot.keyboards import deleted_messages_nav_keyboard, registered_menu_keyboard
from app.bot.states import DeletedMessagesStates
from app.config import AppConfig
from app.repositories.account_repo import AccountRepository
from app.repositories.message_repo import MessageRepository

router = Router()

PAGE_SIZE = 5
BACK_BUTTON = "🔙 بازگشت"
PREV_BUTTON = "◀️ قبلی"
NEXT_BUTTON = "▶️ بعدی"
MENU_BUTTON = "🗑 پیام‌های حذف شده"


def register(dispatcher) -> None:
    dispatcher.include_router(router)


def _retention_cutoff(config: AppConfig) -> datetime:
    return datetime.now().astimezone() - timedelta(days=config.cleanup.retention_days)


def _format_deleted_page(*, messages, page: int, total: int) -> str:
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    lines = [
        f"🗑 <b>پیام‌های حذف شده</b> — صفحه {page + 1}/{total_pages}",
        f"📊 مجموع: {total} پیام",
        "",
    ]
    if not messages:
        lines.append("هیچ پیام حذف‌شده‌ای در ۳ ماه گذشته یافت نشد.")
        return "\n".join(lines)

    for index, msg in enumerate(messages, start=1):
        sender = msg.sender_name or "کاربر"
        received = msg.received_at.strftime("%Y-%m-%d %H:%M") if msg.received_at else "-"
        deleted = msg.deleted_at.strftime("%Y-%m-%d %H:%M") if msg.deleted_at else "-"
        lines.extend(
            [
                f"<b>{index}.</b> 👤 {sender}",
                f"🆔 آیدی: <code>{msg.sender_id}</code>",
                f"📝 {msg.text}",
                f"📥 دریافت: {received} | 🗑 حذف: {deleted}",
                "—" * 20,
            ]
        )
    return "\n".join(lines)


async def _show_deleted_page(
    message: Message,
    state: FSMContext,
    *,
    config: AppConfig,
    session_factory: async_sessionmaker[AsyncSession],
    page: int,
) -> None:
    async with session_factory() as db:
        account = await get_own_account(AccountRepository(db), message.from_user.id)
        if not account:
            await state.clear()
            await message.answer("ابتدا ثبت‌نام کنید.")
            return

        repo = MessageRepository(db)
        since = _retention_cutoff(config)
        total = await repo.count_deleted_since(account_id=account.id, since=since)
        messages = await repo.list_deleted_since(
            account_id=account.id,
            since=since,
            offset=page * PAGE_SIZE,
            limit=PAGE_SIZE,
        )

    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    has_prev = page > 0
    has_next = (page + 1) * PAGE_SIZE < total

    await state.set_state(DeletedMessagesStates.browsing)
    await state.update_data(deleted_page=page)
    await message.answer(
        _format_deleted_page(messages=messages, page=page, total=total),
        reply_markup=deleted_messages_nav_keyboard(has_prev=has_prev, has_next=has_next),
        protect_content=True,
    )


@router.message(F.text == MENU_BUTTON)
async def show_deleted_messages(
    message: Message,
    state: FSMContext,
    config: AppConfig,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as db:
        account = await get_own_account(AccountRepository(db), message.from_user.id)
    if not account:
        await message.answer("ابتدا ثبت‌نام کنید.")
        return

    await _show_deleted_page(
        message,
        state,
        config=config,
        session_factory=session_factory,
        page=0,
    )


@router.message(DeletedMessagesStates.browsing, F.text == PREV_BUTTON)
async def deleted_messages_prev(
    message: Message,
    state: FSMContext,
    config: AppConfig,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    data = await state.get_data()
    page = max(0, int(data.get("deleted_page", 0)) - 1)
    await _show_deleted_page(
        message,
        state,
        config=config,
        session_factory=session_factory,
        page=page,
    )


@router.message(DeletedMessagesStates.browsing, F.text == NEXT_BUTTON)
async def deleted_messages_next(
    message: Message,
    state: FSMContext,
    config: AppConfig,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    data = await state.get_data()
    page = int(data.get("deleted_page", 0)) + 1
    await _show_deleted_page(
        message,
        state,
        config=config,
        session_factory=session_factory,
        page=page,
    )


@router.message(DeletedMessagesStates.browsing, F.text == BACK_BUTTON)
async def deleted_messages_back(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "منوی اصلی:",
        reply_markup=registered_menu_keyboard(),
    )
