from __future__ import annotations

from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.access import get_own_account
from app.bot.keyboards import registered_menu_keyboard
from app.modules.automation.repository import AutomationRepository
from app.modules.automation.states import AutomationStates
from app.repositories.account_repo import AccountRepository

router = Router()

SCHEDULE_MENU = "⏰ پیام زمان‌بندی"
REMINDER_MENU = "🔔 یادآور"
BACK_BUTTON = "🔙 بازگشت"


@router.message(F.text == SCHEDULE_MENU)
async def start_schedule(message: Message, state: FSMContext) -> None:
    await state.set_state(AutomationStates.schedule_peer)
    await message.answer(
        "آیدی عددی مخاطب را ارسال کنید:",
        reply_markup=registered_menu_keyboard(),
    )


@router.message(AutomationStates.schedule_peer, F.text.regexp(r"^-?\d+$"))
async def schedule_peer(
    message: Message,
    state: FSMContext,
) -> None:
    await state.update_data(peer_id=int(message.text))
    await state.set_state(AutomationStates.schedule_text)
    await message.answer("متن پیام را ارسال کنید:")


@router.message(AutomationStates.schedule_text)
async def schedule_text(
    message: Message,
    state: FSMContext,
) -> None:
    await state.update_data(text=message.text or "")
    await state.set_state(AutomationStates.schedule_time)
    await message.answer(
        "زمان ارسال را به فرمت <code>YYYY-MM-DD HH:MM</code> بفرستید\n"
        "مثال: <code>2026-07-01 09:00</code>"
    )


@router.message(AutomationStates.schedule_time)
async def schedule_time(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    try:
        send_at = datetime.strptime((message.text or "").strip(), "%Y-%m-%d %H:%M")
        send_at = send_at.astimezone()
    except ValueError:
        await message.answer("فرمت زمان نامعتبر است.")
        return

    data = await state.get_data()
    async with session_factory() as db:
        account = await get_own_account(AccountRepository(db), message.from_user.id)
        if not account:
            await state.clear()
            return
        await AutomationRepository(db).add_scheduled(
            account_id=account.id,
            peer_id=int(data["peer_id"]),
            text=str(data["text"]),
            send_at=send_at,
        )
        await db.commit()

    await state.clear()
    await message.answer(
        f"✅ پیام برای {send_at.strftime('%Y-%m-%d %H:%M')} زمان‌بندی شد.",
        reply_markup=registered_menu_keyboard(),
    )


@router.message(F.text == REMINDER_MENU)
async def start_reminder(message: Message, state: FSMContext) -> None:
    await state.set_state(AutomationStates.reminder_text)
    await message.answer("متن یادآور را ارسال کنید:")


@router.message(AutomationStates.reminder_text)
async def reminder_text(message: Message, state: FSMContext) -> None:
    await state.update_data(reminder_text=message.text or "")
    await state.set_state(AutomationStates.reminder_time)
    await message.answer(
        "زمان یادآور را به فرمت <code>YYYY-MM-DD HH:MM</code> بفرستید:"
    )


@router.message(AutomationStates.reminder_time)
async def reminder_time(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    try:
        remind_at = datetime.strptime((message.text or "").strip(), "%Y-%m-%d %H:%M")
        remind_at = remind_at.astimezone()
    except ValueError:
        await message.answer("فرمت زمان نامعتبر است.")
        return

    data = await state.get_data()
    async with session_factory() as db:
        account = await get_own_account(AccountRepository(db), message.from_user.id)
        if not account:
            await state.clear()
            return
        await AutomationRepository(db).add_reminder(
            account_id=account.id,
            text=str(data["reminder_text"]),
            remind_at=remind_at,
        )
        await db.commit()

    await state.clear()
    await message.answer(
        f"✅ یادآور برای {remind_at.strftime('%Y-%m-%d %H:%M')} ثبت شد.",
        reply_markup=registered_menu_keyboard(),
    )
