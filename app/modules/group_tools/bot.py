from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.access import get_own_account
from app.bot.keyboards import registered_menu_keyboard
from app.modules.group_tools.states import GroupToolsStates
from app.modules.settings.repository import MonitoredChatRepository, TrackedTargetRepository
from app.repositories.account_repo import AccountRepository

router = Router()

TRACK_MENU = "👁 ردیابی فرد"
GROUP_MENU = "👥 گروه‌های تحت‌نظر"
BACK_BUTTON = "🔙 بازگشت"


@router.message(F.text == TRACK_MENU)
async def track_menu(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as db:
        account = await get_own_account(AccountRepository(db), message.from_user.id)
        if not account:
            await message.answer("ابتدا ثبت‌نام کنید.")
            return
        targets = await TrackedTargetRepository(db).list_for_account(account.id)

    lines = ["👁 <b>ردیابی فرد</b>", ""]
    if targets:
        for t in targets:
            label = t.label or "-"
            lines.append(f"• <code>{t.target_user_id}</code> — {label}")
    else:
        lines.append("هیچ فردی ردیابی نمی‌شود.")

    lines.extend(
        [
            "",
            "برای افزودن: آیدی عددی یا فوروارد پیام فرد را بفرستید.",
            "برای حذف: /untrack &lt;آیدی&gt;",
        ]
    )
    await state.set_state(GroupToolsStates.track_add)
    await message.answer("\n".join(lines))


@router.message(GroupToolsStates.track_add, F.forward_from)
async def track_from_forward(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = message.forward_from.id
    await _add_target(message, state, session_factory, user_id)


@router.message(GroupToolsStates.track_add, F.text.regexp(r"^-?\d+$"))
async def track_from_id(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _add_target(message, state, session_factory, int(message.text))


@router.message(GroupToolsStates.track_add, F.text == BACK_BUTTON)
async def track_back(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("منوی اصلی:", reply_markup=registered_menu_keyboard())


@router.message(F.text.regexp(r"^/untrack\s+-?\d+$"))
async def untrack_user(
    message: Message,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = int((message.text or "").split()[1])
    async with session_factory() as db:
        account = await get_own_account(AccountRepository(db), message.from_user.id)
        if not account:
            return
        removed = await TrackedTargetRepository(db).remove(
            account_id=account.id, target_user_id=user_id
        )
        await db.commit()
    if removed:
        await message.answer(f"✅ ردیابی <code>{user_id}</code> حذف شد.")
    else:
        await message.answer("فردی با این آیدی ردیابی نمی‌شد.")


async def _add_target(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker[AsyncSession],
    user_id: int,
) -> None:
    async with session_factory() as db:
        account = await get_own_account(AccountRepository(db), message.from_user.id)
        if not account:
            await state.clear()
            await message.answer("ابتدا ثبت‌نام کنید.")
            return
        await TrackedTargetRepository(db).add(
            account_id=account.id,
            target_user_id=user_id,
        )
        await db.commit()

    await state.clear()
    await message.answer(
        f"✅ فرد <code>{user_id}</code> به لیست ردیابی اضافه شد.\n"
        "تغییرات پروفایل، آنلاین‌بودن و پیام‌هایش ردیابی می‌شود.",
        reply_markup=registered_menu_keyboard(),
    )


@router.message(F.text == GROUP_MENU)
async def group_menu(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as db:
        account = await get_own_account(AccountRepository(db), message.from_user.id)
        if not account:
            await message.answer("ابتدا ثبت‌نام کنید.")
            return
        chats = await MonitoredChatRepository(db).list_for_account(account.id)

    lines = ["👥 <b>گروه‌های تحت‌نظر</b>", ""]
    if chats:
        for c in chats:
            title = c.title or "-"
            lines.append(f"• <code>{c.chat_id}</code> — {title}")
    else:
        lines.append("هیچ گروهی تحت‌نظر نیست.")

    lines.extend(
        [
            "",
            "برای افزودن: یک پیام از گروه را فوروارد کنید یا آیدی گروه (منفی) را بفرستید.",
            "برای حذف: /ungroup &lt;chat_id&gt;",
        ]
    )
    await state.set_state(GroupToolsStates.group_add)
    await message.answer("\n".join(lines))


@router.message(GroupToolsStates.group_add, F.forward_from_chat)
async def group_from_forward(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    chat = message.forward_from_chat
    if not chat:
        return
    await _add_group(
        message, state, session_factory, chat.id, getattr(chat, "title", None)
    )


@router.message(GroupToolsStates.group_add, F.text.regexp(r"^-\d+$"))
async def group_from_id(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _add_group(message, state, session_factory, int(message.text), None)


@router.message(GroupToolsStates.group_add, F.text == BACK_BUTTON)
async def group_back(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("منوی اصلی:", reply_markup=registered_menu_keyboard())


@router.message(F.text.regexp(r"^/ungroup\s+-\d+$"))
async def ungroup_chat(
    message: Message,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    chat_id = int((message.text or "").split()[1])
    async with session_factory() as db:
        account = await get_own_account(AccountRepository(db), message.from_user.id)
        if not account:
            return
        removed = await MonitoredChatRepository(db).remove(
            account_id=account.id, chat_id=chat_id
        )
        await db.commit()
    if removed:
        await message.answer(f"✅ گروه <code>{chat_id}</code> از لیست حذف شد.")
    else:
        await message.answer("این گروه در لیست نبود.")


async def _add_group(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker[AsyncSession],
    chat_id: int,
    title: str | None,
) -> None:
    async with session_factory() as db:
        account = await get_own_account(AccountRepository(db), message.from_user.id)
        if not account:
            await state.clear()
            await message.answer("ابتدا ثبت‌نام کنید.")
            return
        await MonitoredChatRepository(db).add(
            account_id=account.id,
            chat_id=chat_id,
            title=title,
        )
        await db.commit()

    await state.clear()
    await message.answer(
        f"✅ گروه <code>{chat_id}</code> اضافه شد.\n"
        "پیام‌های حذف‌شده در این گروه ذخیره و اعلان می‌شوند.",
        reply_markup=registered_menu_keyboard(),
    )
