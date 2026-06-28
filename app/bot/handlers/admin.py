from __future__ import annotations

from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.filters import SuperAdminFilter
from app.bot.keyboards import admin_menu_keyboard, main_menu_keyboard
from app.bot.service_context import ServiceContext
from app.bot.states import AdminStates
from app.config import AppConfig
from app.db.models import Account, StoredMessage
from app.repositories.account_repo import AccountRepository
from app.repositories.message_repo import MessageRepository
from app.services.account_lifecycle import delete_account

router = Router()
router.message.filter(SuperAdminFilter())

ADMIN_PANEL_TEXT = (
    "🛡 <b>پنل سوپرادمین</b>\n\n"
    "از دکمه‌های زیر یا دستورات استفاده کنید:\n"
    "• /stats — آمار کلی\n"
    "• /users — لیست کاربران\n"
    "• /user &lt;id&gt; — جزئیات و فعالیت کاربر\n"
    "• /delete &lt;id&gt; — حذف کامل کاربر\n"
    "• /activate &lt;id&gt; — فعال‌سازی\n"
    "• /deactivate &lt;id&gt; — غیرفعال‌سازی\n"
    "• /recent — فعالیت اخیر (پیام‌های حذف‌شده)"
)


def register(dispatcher) -> None:
    dispatcher.include_router(router)


def _format_account_line(acc: Account) -> str:
    username = f"@{acc.username}" if acc.username else "-"
    state = "✅" if acc.is_active else "⛔"
    name = acc.display_name or "-"
    return (
        f"{state} <b>id={acc.id}</b> {username}\n"
        f"   📱 {acc.phone} | 👤 {name}\n"
        f"   🎁 ref={acc.referral_code or '-'} | tg={acc.telegram_id}"
    )


async def _format_user_details(
    db: AsyncSession,
    account: Account,
) -> str:
    stats = await MessageRepository(db).get_account_stats(account.id)
    username = f"@{account.username}" if account.username else "-"
    state = "فعال ✅" if account.is_active else "غیرفعال ⛔"
    last_recv = stats["last_received"]
    last_del = stats["last_deleted"]

    def _fmt_dt(value: datetime | None) -> str:
        if not value:
            return "-"
        return value.strftime("%Y-%m-%d %H:%M")

    return (
        f"👤 <b>جزئیات کاربر id={account.id}</b>\n\n"
        f"وضعیت: {state}\n"
        f"نام: {account.display_name or '-'}\n"
        f"یوزرنیم: {username}\n"
        f"شماره: <code>{account.phone}</code>\n"
        f"تلگرام ID: <code>{account.telegram_id}</code>\n"
        f"بات چت ID: <code>{account.bot_chat_id or '-'}</code>\n"
        f"کد معرف: <code>{account.referral_code or '-'}</code>\n"
        f"معرفی‌شده توسط: {account.referred_by or '-'}\n"
        f"تاریخ ثبت: {_fmt_dt(account.created_at)}\n\n"
        f"📊 <b>فعالیت:</b>\n"
        f"• پیام ذخیره‌شده: {stats['total']}\n"
        f"• پیام حذف‌شده: {stats['deleted']}\n"
        f"• آخرین پیام دریافتی: {_fmt_dt(last_recv if isinstance(last_recv, datetime) else None)}\n"
        f"• آخرین حذف گزارش‌شده: {_fmt_dt(last_del if isinstance(last_del, datetime) else None)}"
    )


async def _send_stats(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as db:
        total = await db.scalar(select(func.count()).select_from(Account)) or 0
        active = await db.scalar(
            select(func.count()).select_from(Account).where(Account.is_active.is_(True))
        ) or 0
        stored = await db.scalar(select(func.count()).select_from(StoredMessage)) or 0
        deleted = await db.scalar(
            select(func.count())
            .select_from(StoredMessage)
            .where(StoredMessage.deleted_at.is_not(None))
        ) or 0

    await message.answer(
        "📊 <b>آمار سرویس</b>\n\n"
        f"👥 کل کاربران: {total}\n"
        f"✅ فعال: {active}\n"
        f"💬 پیام ذخیره‌شده: {stored}\n"
        f"🗑 حذف‌شده: {deleted}",
        reply_markup=admin_menu_keyboard(),
    )


async def _send_users_list(
    message: Message,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as db:
        result = await db.execute(select(Account).order_by(Account.id))
        accounts = list(result.scalars().all())

    if not accounts:
        await message.answer("هیچ کاربری ثبت نشده.", reply_markup=admin_menu_keyboard())
        return

    lines = ["👥 <b>لیست کاربران</b>", ""]
    for acc in accounts[:30]:
        lines.append(_format_account_line(acc))
    if len(accounts) > 30:
        lines.append(f"\n... و {len(accounts) - 30} کاربر دیگر")

    await message.answer("\n".join(lines), reply_markup=admin_menu_keyboard())


async def _send_recent_activity(
    message: Message,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as db:
        recent = await MessageRepository(db).list_recent_activity(limit=15)
        if not recent:
            await message.answer(
                "فعالیت اخیری ثبت نشده.",
                reply_markup=admin_menu_keyboard(),
            )
            return

        account_ids = {msg.account_id for msg in recent}
        result = await db.execute(select(Account).where(Account.id.in_(account_ids)))
        accounts = {acc.id: acc for acc in result.scalars().all()}

    lines = ["📈 <b>فعالیت اخیر</b> (پیام‌های حذف‌شده)", ""]
    for msg in recent:
        acc = accounts.get(msg.account_id)
        label = f"@{acc.username}" if acc and acc.username else f"id={msg.account_id}"
        when = msg.deleted_at.strftime("%m-%d %H:%M") if msg.deleted_at else "-"
        preview = (msg.text or "")[:60].replace("\n", " ")
        lines.append(f"🗑 {when} | {label}\n   «{preview}»")

    await message.answer("\n".join(lines), reply_markup=admin_menu_keyboard())


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(ADMIN_PANEL_TEXT, reply_markup=admin_menu_keyboard())


@router.message(F.text == "🔙 خروج از پنل")
async def exit_admin_panel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("خارج شدید از پنل ادمین.", reply_markup=main_menu_keyboard())


@router.message(Command("stats"))
@router.message(F.text == "📊 آمار سرویس")
async def cmd_stats(
    message: Message,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _send_stats(message, session_factory)


@router.message(Command("users"))
@router.message(F.text == "👥 لیست کاربران")
async def cmd_users(
    message: Message,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _send_users_list(message, session_factory)


@router.message(Command("recent"))
@router.message(F.text == "📈 فعالیت اخیر")
async def cmd_recent(
    message: Message,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _send_recent_activity(message, session_factory)


@router.message(Command("user"))
async def cmd_user(
    message: Message,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("استفاده: /user &lt;id&gt;")
        return

    account_id = int(parts[1])
    async with session_factory() as db:
        account = await AccountRepository(db).get_by_id(account_id)
        if not account:
            await message.answer(f"کاربر {account_id} پیدا نشد.")
            return
        text = await _format_user_details(db, account)

    await message.answer(text, reply_markup=admin_menu_keyboard())


@router.message(F.text == "🔍 جزئیات کاربر")
async def ask_user_id_details(message: Message, state: FSMContext) -> None:
    await state.set_state(AdminStates.waiting_user_id_details)
    await message.answer(
        "شناسه کاربر (id) را ارسال کنید:",
        reply_markup=admin_menu_keyboard(),
    )


@router.message(AdminStates.waiting_user_id_details, F.text.regexp(r"^\d+$"))
async def receive_user_id_details(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    account_id = int(message.text)
    async with session_factory() as db:
        account = await AccountRepository(db).get_by_id(account_id)
        if not account:
            await message.answer(f"کاربر {account_id} پیدا نشد.")
            await state.clear()
            return
        text = await _format_user_details(db, account)

    await state.clear()
    await message.answer(text, reply_markup=admin_menu_keyboard())


@router.message(Command("delete"))
async def cmd_delete(
    message: Message,
    state: FSMContext,
    config: AppConfig,
    session_factory: async_sessionmaker[AsyncSession],
    service_context: ServiceContext | None = None,
) -> None:
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("استفاده: /delete &lt;id&gt;")
        return

    account_id = int(parts[1])
    async with session_factory() as db:
        account = await AccountRepository(db).get_by_id(account_id)
        if not account:
            await message.answer(f"کاربر {account_id} پیدا نشد.")
            return

    await state.update_data(delete_account_id=account_id)
    await state.set_state(AdminStates.waiting_delete_confirm)
    username = f"@{account.username}" if account.username else account.phone
    await message.answer(
        f"⚠️ حذف کاربر <b>id={account_id}</b> ({username})؟\n"
        "سشن و تمام پیام‌های ذخیره‌شده حذف می‌شوند.\n\n"
        "برای تأیید «بله» و برای انصراف «خیر» بنویسید.",
        reply_markup=admin_menu_keyboard(),
    )


@router.message(F.text == "🗑 حذف کاربر")
async def ask_user_id_delete(message: Message, state: FSMContext) -> None:
    await state.set_state(AdminStates.waiting_user_id_delete)
    await message.answer(
        "شناسه کاربر (id) را برای حذف ارسال کنید:",
        reply_markup=admin_menu_keyboard(),
    )


@router.message(AdminStates.waiting_user_id_delete, F.text.regexp(r"^\d+$"))
async def receive_user_id_delete(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    account_id = int(message.text)
    async with session_factory() as db:
        account = await AccountRepository(db).get_by_id(account_id)
        if not account:
            await message.answer(f"کاربر {account_id} پیدا نشد.")
            await state.clear()
            return

    await state.update_data(delete_account_id=account_id)
    await state.set_state(AdminStates.waiting_delete_confirm)
    username = f"@{account.username}" if account.username else account.phone
    await message.answer(
        f"⚠️ حذف کاربر <b>id={account_id}</b> ({username})؟\n"
        "سشن و تمام پیام‌های ذخیره‌شده حذف می‌شوند.\n\n"
        "برای تأیید «بله» و برای انصراف «خیر» بنویسید.",
        reply_markup=admin_menu_keyboard(),
    )


@router.message(AdminStates.waiting_delete_confirm, F.text.casefold().in_({"بله", "yes"}))
async def confirm_delete_user(
    message: Message,
    state: FSMContext,
    config: AppConfig,
    session_factory: async_sessionmaker[AsyncSession],
    service_context: ServiceContext | None = None,
) -> None:
    data = await state.get_data()
    account_id = data.get("delete_account_id")
    if not account_id:
        await state.clear()
        await message.answer("درخواست منقضی شد.")
        return

    pool = service_context.pool if service_context else None
    async with session_factory() as db:
        deleted = await delete_account(config, db, int(account_id), pool=pool)

    await state.clear()
    if deleted:
        await message.answer(
            f"🗑 کاربر {account_id} حذف شد. سشن منقضی و داده‌ها پاک شدند.",
            reply_markup=admin_menu_keyboard(),
        )
    else:
        await message.answer(
            f"کاربر {account_id} پیدا نشد.",
            reply_markup=admin_menu_keyboard(),
        )


@router.message(AdminStates.waiting_delete_confirm)
async def cancel_delete_user(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("حذف لغو شد.", reply_markup=admin_menu_keyboard())


@router.message(Command("activate"))
async def cmd_activate(
    message: Message,
    session_factory: async_sessionmaker[AsyncSession],
    service_context: ServiceContext | None = None,
) -> None:
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("استفاده: /activate &lt;id&gt;")
        return

    account_id = int(parts[1])
    async with session_factory() as db:
        repo = AccountRepository(db)
        account = await repo.get_by_id(account_id)
        if not account:
            await message.answer(f"کاربر {account_id} پیدا نشد.")
            return
        await repo.set_active(account_id, True)
        await db.commit()
        await db.refresh(account)

    if service_context is not None:
        try:
            await service_context.on_new_account(account)
            await message.answer(
                f"✅ کاربر {account_id} فعال شد و مانیتورینگ شروع شد.",
                reply_markup=admin_menu_keyboard(),
            )
            return
        except Exception:
            pass

    await message.answer(
        f"✅ کاربر {account_id} فعال شد. برای مانیتور، سرویس را restart کنید.",
        reply_markup=admin_menu_keyboard(),
    )


@router.message(Command("deactivate"))
async def cmd_deactivate(
    message: Message,
    session_factory: async_sessionmaker[AsyncSession],
    service_context: ServiceContext | None = None,
) -> None:
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("استفاده: /deactivate &lt;id&gt;")
        return

    account_id = int(parts[1])
    async with session_factory() as db:
        repo = AccountRepository(db)
        account = await repo.get_by_id(account_id)
        if not account:
            await message.answer(f"کاربر {account_id} پیدا نشد.")
            return
        await repo.set_active(account_id, False)
        await db.commit()

    if service_context is not None:
        await service_context.pool.stop_account(account_id)

    await message.answer(
        f"⛔ کاربر {account_id} غیرفعال شد.",
        reply_markup=admin_menu_keyboard(),
    )
