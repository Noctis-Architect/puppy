from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    MessageOriginChannel,
    MessageOriginChat,
    MessageOriginUser,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.access import get_own_account
from app.bot.concurrency import account_client_lock
from app.bot.keyboards import registered_menu_keyboard
from app.bot.service_context import ServiceContext
from app.modules.group_tools.states import GroupToolsStates
from app.modules.settings.repository import MonitoredChatRepository, TrackedTargetRepository
from app.repositories.account_repo import AccountRepository
from app.telegram.client_utils import SessionExpiredError, ensure_client_connected

router = Router()
logger = logging.getLogger(__name__)

TRACK_MENU = "👁 ردیابی فرد"
GROUP_MENU = "👥 گروه‌های تحت‌نظر"
BACK_BUTTON = "🔙 بازگشت"


def _forwarded_user_id(message: Message) -> int | None:
    origin = message.forward_origin
    if isinstance(origin, MessageOriginUser):
        return origin.sender_user.id
    if message.forward_from:
        return message.forward_from.id
    return None


def _forwarded_group_info(message: Message) -> tuple[int, str | None] | None:
    origin = message.forward_origin
    if isinstance(origin, MessageOriginChannel):
        return origin.chat.id, origin.chat.title
    if isinstance(origin, MessageOriginChat):
        return origin.sender_chat.id, origin.sender_chat.title
    if message.forward_from_chat:
        chat = message.forward_from_chat
        return chat.id, getattr(chat, "title", None)
    return None


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
            "برای افزودن: آیدی عددی، @یوزرنیم، یا فوروارد پیام فرد را بفرستید.",
            "برای حذف: /untrack &lt;آیدی&gt;",
        ]
    )
    await state.set_state(GroupToolsStates.track_add)
    await message.answer("\n".join(lines))


@router.message(GroupToolsStates.track_add, F.forward_origin)
async def track_from_forward(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = _forwarded_user_id(message)
    if user_id is None:
        await message.answer("فقط فوروارد پیام از یک کاربر پشتیبانی می‌شود.")
        return
    await _add_target(message, state, session_factory, user_id)


@router.message(GroupToolsStates.track_add, F.text.regexp(r"^-?\d+$"))
async def track_from_id(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _add_target(message, state, session_factory, int(message.text))


@router.message(GroupToolsStates.track_add, F.text.regexp(r"^@?[A-Za-z][A-Za-z0-9_]{4,31}$"))
async def track_from_username(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker[AsyncSession],
    service_context: ServiceContext | None,
) -> None:
    username = (message.text or "").strip().lstrip("@")
    async with session_factory() as db:
        account = await get_own_account(AccountRepository(db), message.from_user.id)
    if not account:
        await message.answer("ابتدا ثبت‌نام کنید.")
        return
    if service_context is None or account.id not in service_context.pool.clients:
        await message.answer("اتصال اکانت شما فعال نیست. لطفاً چند لحظه صبر کنید.")
        return

    managed = service_context.pool.clients[account.id]
    lock = account_client_lock(account.id)
    async with lock:
        try:
            await ensure_client_connected(managed.client)
            entity = await managed.client.get_entity(username)
        except SessionExpiredError:
            await message.answer("سشن تلگرام منقضی شده. دوباره ثبت‌نام کنید.")
            return
        except Exception:
            logger.warning("Could not resolve username @%s", username, exc_info=True)
            await message.answer(f"کاربر @{username} پیدا نشد.")
            return

    await _add_target(message, state, session_factory, entity.id, label=f"@{username}")


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
    *,
    label: str | None = None,
) -> None:
    async with session_factory() as db:
        account = await get_own_account(AccountRepository(db), message.from_user.id)
        if not account:
            await state.clear()
            await message.answer("ابتدا ثبت‌نام کنید.")
            return
        if await TrackedTargetRepository(db).is_tracked(
            account_id=account.id, target_user_id=user_id
        ):
            await state.clear()
            await message.answer(
                f"فرد <code>{user_id}</code> قبلاً در لیست ردیابی است.",
                reply_markup=registered_menu_keyboard(),
            )
            return
        await TrackedTargetRepository(db).add(
            account_id=account.id,
            target_user_id=user_id,
            label=label,
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


@router.message(GroupToolsStates.group_add, F.forward_origin)
async def group_from_forward(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    info = _forwarded_group_info(message)
    if info is None:
        await message.answer("فقط فوروارد پیام از گروه یا کانال پشتیبانی می‌شود.")
        return
    chat_id, title = info
    await _add_group(message, state, session_factory, chat_id, title)


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
        if await MonitoredChatRepository(db).is_listed(
            account_id=account.id, chat_id=chat_id
        ):
            await state.clear()
            await message.answer(
                f"گروه <code>{chat_id}</code> قبلاً در لیست است.",
                reply_markup=registered_menu_keyboard(),
            )
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
