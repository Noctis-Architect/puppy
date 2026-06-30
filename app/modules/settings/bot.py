from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.access import get_own_account
from app.bot.keyboards import registered_menu_keyboard
from app.modules.settings.repository import AccountSettingsRepository
from app.modules.settings.states import SettingsStates
from app.repositories.account_repo import AccountRepository

router = Router()

MENU_BUTTON = "⚙️ تنظیمات"
BACK_BUTTON = "🔙 بازگشت"

TOGGLE_FIELDS = {
    "📥 آرشیو مدیا": "archive_media",
    "✏️ ردیاب ادیت": "track_edits",
    "🟢 ردیاب آنلاین": "track_presence",
    "👤 ردیاب پروفایل": "track_profile",
    "📖 ردیاب استوری": "track_stories",
    "⌨️ هشدار تایپینگ": "typing_alerts",
    "🤖 شناسایی خودکار ناشناس": "auto_anon_reveal",
    "📣 هشدار منشن گروه": "group_mention_alerts",
    "👥 هشدار عضو گروه": "group_member_alerts",
    "📊 خلاصه روزانه": "daily_summary",
    "💤 حالت نیستم": "away_mode_enabled",
    "💾 بکاپ پیام خودم": "backup_own_messages",
}


def _settings_keyboard(settings) -> list[list[str]]:
    rows: list[list[str]] = []
    for label, field in TOGGLE_FIELDS.items():
        state = "✅" if getattr(settings, field, False) else "❌"
        rows.append([f"{state} {label}"])
    rows.append([BACK_BUTTON])
    return rows


def _format_settings(settings) -> str:
    lines = ["⚙️ <b>تنظیمات</b>", "", "روی هر گزینه بزنید تا روشن/خاموش شود:", ""]
    for label, field in TOGGLE_FIELDS.items():
        state = "روشن" if getattr(settings, field, False) else "خاموش"
        lines.append(f"• {label}: {state}")
    if settings.away_mode_enabled:
        preview = (settings.away_message or "تنظیم نشده")[:80]
        lines.extend(["", f"💤 متن «نیستم»: {preview}"])
    return "\n".join(lines)


@router.message(F.text == MENU_BUTTON)
async def show_settings(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as db:
        account = await get_own_account(AccountRepository(db), message.from_user.id)
        if not account:
            await message.answer("ابتدا ثبت‌نام کنید.")
            return
        settings = await AccountSettingsRepository(db).get_or_create(account.id)
        await db.commit()

    await state.set_state(SettingsStates.menu)
    from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

    rows = [[KeyboardButton(text=row[0])] for row in _settings_keyboard(settings)]
    await message.answer(
        _format_settings(settings),
        reply_markup=ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True),
    )


@router.message(SettingsStates.menu, F.text == BACK_BUTTON)
async def settings_back(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("منوی اصلی:", reply_markup=registered_menu_keyboard())


@router.message(SettingsStates.menu)
async def toggle_setting(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    text = (message.text or "").strip()
    field = None
    for label, fname in TOGGLE_FIELDS.items():
        if text.endswith(label) or label in text:
            field = fname
            break

    if not field:
        await message.answer("گزینه نامعتبر. از دکمه‌های منو استفاده کنید.")
        return

    async with session_factory() as db:
        account = await get_own_account(AccountRepository(db), message.from_user.id)
        if not account:
            await state.clear()
            await message.answer("ابتدا ثبت‌نام کنید.")
            return
        settings = await AccountSettingsRepository(db).toggle(account.id, field)
        await db.commit()

    if field == "away_mode_enabled" and settings.away_mode_enabled and not settings.away_message:
        await state.set_state(SettingsStates.away_message)
        await message.answer(
            "💤 حالت «نیستم» روشن شد.\nمتن پاسخ خودکار را بفرستید:",
        )
        return

    from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

    rows = [[KeyboardButton(text=row[0])] for row in _settings_keyboard(settings)]
    await message.answer(
        _format_settings(settings),
        reply_markup=ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True),
    )


@router.message(SettingsStates.away_message, F.text == BACK_BUTTON)
async def away_message_back(message: Message, state: FSMContext) -> None:
    await state.set_state(SettingsStates.menu)
    await message.answer("تنظیم متن لغو شد. از منوی تنظیمات ادامه دهید.")


@router.message(SettingsStates.away_message)
async def save_away_message(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("متن خالی است. دوباره بفرستید یا «🔙 بازگشت» بزنید.")
        return

    async with session_factory() as db:
        account = await get_own_account(AccountRepository(db), message.from_user.id)
        if not account:
            await state.clear()
            await message.answer("ابتدا ثبت‌نام کنید.")
            return
        settings = await AccountSettingsRepository(db).get_or_create(account.id)
        settings.away_message = text
        await db.commit()

    await state.set_state(SettingsStates.menu)
    from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

    rows = [[KeyboardButton(text=row[0])] for row in _settings_keyboard(settings)]
    await message.answer(
        "✅ متن «نیستم» ذخیره شد.\n\n" + _format_settings(settings),
        reply_markup=ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True),
    )
