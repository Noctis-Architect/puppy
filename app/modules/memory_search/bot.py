from __future__ import annotations

from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.access import get_own_account
from app.bot.keyboards import registered_menu_keyboard
from app.modules.archive.repository import MessageRepository
from app.modules.contact_tracking.repository import ContactTrackingRepository
from app.modules.memory_search.states import MemorySearchStates
from app.repositories.account_repo import AccountRepository

router = Router()

SEARCH_MENU = "🔎 جستجو"
PROFILE_MENU = "📋 پروفایل مخاطب"
EXPORT_MENU = "📤 اکسپورت مکالمه"
BACK_BUTTON = "🔙 بازگشت"


@router.message(F.text == SEARCH_MENU)
async def start_search(message: Message, state: FSMContext) -> None:
    await state.set_state(MemorySearchStates.waiting_query)
    await message.answer(
        "عبارت جستجو را ارسال کنید:",
        reply_markup=registered_menu_keyboard(),
    )


@router.message(MemorySearchStates.waiting_query, F.text == BACK_BUTTON)
async def search_back(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("منوی اصلی:", reply_markup=registered_menu_keyboard())


@router.message(MemorySearchStates.waiting_query)
async def process_search(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    query = (message.text or "").strip()
    if not query:
        await message.answer("عبارت خالی است.")
        return

    async with session_factory() as db:
        account = await get_own_account(AccountRepository(db), message.from_user.id)
        if not account:
            await state.clear()
            await message.answer("ابتدا ثبت‌نام کنید.")
            return
        results = await MessageRepository(db).search_text(
            account_id=account.id, query=query, limit=15
        )

    await state.clear()
    if not results:
        await message.answer("نتیجه‌ای یافت نشد.", reply_markup=registered_menu_keyboard())
        return

    lines = [f"🔎 نتایج برای «{query}»", ""]
    for msg in results:
        sender = msg.sender_name or "کاربر"
        when = msg.received_at.strftime("%m-%d %H:%M") if msg.received_at else "-"
        preview = (msg.text or "")[:80]
        lines.append(f"👤 {sender} ({when})\n📝 {preview}\n—")

    await message.answer("\n".join(lines), reply_markup=registered_menu_keyboard(), protect_content=True)


@router.message(F.text == PROFILE_MENU)
async def start_profile(message: Message, state: FSMContext) -> None:
    await state.set_state(MemorySearchStates.waiting_profile_id)
    await message.answer(
        "آیدی عددی مخاطب را ارسال کنید:",
        reply_markup=registered_menu_keyboard(),
    )


@router.message(MemorySearchStates.waiting_profile_id, F.text.regexp(r"^-?\d+$"))
async def show_profile(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    target_id = int(message.text)
    async with session_factory() as db:
        account = await get_own_account(AccountRepository(db), message.from_user.id)
        if not account:
            await state.clear()
            return
        msgs = await MessageRepository(db).list_by_sender(
            account_id=account.id, sender_id=target_id, limit=10
        )
        changes = await ContactTrackingRepository(db).list_profile_changes(
            account_id=account.id, target_user_id=target_id, limit=5
        )
        presence = await ContactTrackingRepository(db).list_presence(
            account_id=account.id, target_user_id=target_id, limit=5
        )
        stories = await ContactTrackingRepository(db).list_stories(
            account_id=account.id, target_user_id=target_id, limit=5
        )
        deleted = await MessageRepository(db).list_by_sender(
            account_id=account.id, sender_id=target_id, limit=10, deleted_only=True
        )

    await state.clear()
    lines = [f"📋 <b>پروفایل مخاطب</b> <code>{target_id}</code>", ""]
    lines.append("<b>پیام‌های اخیر:</b>")
    if msgs:
        for m in msgs:
            flag = " 🗑" if m.deleted_at else ""
            lines.append(f"• {m.text[:60]}{flag}")
    else:
        lines.append("• —")

    lines.append("\n<b>پیام‌های حذف‌شده:</b>")
    if deleted:
        for m in deleted:
            lines.append(f"• {m.text[:60]}")
    else:
        lines.append("• —")

    lines.append("\n<b>تغییرات پروفایل:</b>")
    if changes:
        for c in changes:
            lines.append(f"• {c.field}: {c.old_value or '-'} → {c.new_value or '-'}")
    else:
        lines.append("• —")

    lines.append("\n<b>آنلاین/آفلاین:</b>")
    if presence:
        for p in presence:
            when = p.at.strftime("%m-%d %H:%M") if p.at else "-"
            lines.append(f"• {p.status} — {when}")
    else:
        lines.append("• —")

    lines.append("\n<b>استوری‌های ذخیره‌شده:</b>")
    if stories:
        for s in stories:
            when = s.saved_at.strftime("%m-%d %H:%M") if s.saved_at else "-"
            media = "📎" if s.media_path else "—"
            lines.append(f"• {when} {media}")
    else:
        lines.append("• —")

    await message.answer("\n".join(lines), reply_markup=registered_menu_keyboard(), protect_content=True)


@router.message(F.text == EXPORT_MENU)
async def start_export(message: Message, state: FSMContext) -> None:
    await state.set_state(MemorySearchStates.waiting_export_id)
    await message.answer(
        "آیدی عددی مخاطب برای اکسپورت مکالمهٔ حذف‌شده:",
        reply_markup=registered_menu_keyboard(),
    )


@router.message(MemorySearchStates.waiting_export_id, F.text.regexp(r"^-?\d+$"))
async def export_conversation(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    target_id = int(message.text)
    async with session_factory() as db:
        account = await get_own_account(AccountRepository(db), message.from_user.id)
        if not account:
            await state.clear()
            return
        msgs = await MessageRepository(db).list_by_sender(
            account_id=account.id, sender_id=target_id, limit=100
        )

    await state.clear()
    deleted = [m for m in msgs if m.deleted_at]
    lines = [f"مکالمه با {target_id}", "=" * 40, ""]
    for m in deleted or msgs:
        when = m.received_at.strftime("%Y-%m-%d %H:%M") if m.received_at else "-"
        lines.append(f"[{when}] {m.text}")

    content = "\n".join(lines).encode("utf-8")
    doc = BufferedInputFile(content, filename=f"chat_{target_id}.txt")
    await message.answer_document(doc, protect_content=True)
    await message.answer("✅ اکسپورت آماده است.", reply_markup=registered_menu_keyboard())
