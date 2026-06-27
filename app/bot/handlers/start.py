from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.access import get_own_account
from app.bot.keyboards import (
    main_menu_keyboard,
    registered_menu_keyboard,
    share_phone_keyboard,
    unregister_confirm_keyboard,
)
from app.bot.messages import PRIVACY_BANNER, PRIVACY_SHORT, REGISTRATION_WARNING, UNREGISTER_WARNING
from app.bot.service_context import ServiceContext
from app.bot.states import RegistrationStates, UnregisterStates
from app.config import AppConfig
from app.repositories.account_repo import AccountRepository
from app.services.account_lifecycle import delete_account

router = Router()


def register(dispatcher) -> None:
    dispatcher.include_router(router)


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await state.clear()

    async with session_factory() as db:
        existing = await get_own_account(AccountRepository(db), message.from_user.id)

    if existing:
        referral = existing.referral_code or "-"
        await message.answer(
            "👋 سلام! شما قبلاً ثبت‌نام کرده‌اید.\n\n"
            f"{PRIVACY_SHORT}\n\n"
            "از این پس اگر کسی پیام خصوصی‌تان را حذف کند، "
            "متن آن همین‌جا برایتان ارسال می‌شود.\n\n"
            f"🎁 کد معرف شما: <code>{referral}</code>",
            reply_markup=registered_menu_keyboard(),
            protect_content=True,
        )
        return

    await message.answer(
        "👋 به Message Guard خوش آمدید!\n\n"
        f"{PRIVACY_BANNER}\n\n"
        "این سرویس پیام‌های خصوصی شما را ذخیره می‌کند و "
        "اگر طرف مقابل پیامی را حذف کند، همان‌جا به شما اطلاع می‌دهد.\n\n"
        "برای شروع، روی «ثبت‌نام» بزنید.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(F.text == "📝 ثبت‌نام")
async def start_registration(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as db:
        existing = await get_own_account(AccountRepository(db), message.from_user.id)
    if existing:
        await message.answer(
            "شما قبلاً ثبت‌نام کرده‌اید.",
            reply_markup=registered_menu_keyboard(),
        )
        return

    await state.set_state(RegistrationStates.waiting_phone)
    await message.answer(REGISTRATION_WARNING, reply_markup=share_phone_keyboard())


@router.message(F.text == "🎁 کد معرف من")
async def show_my_referral_code(
    message: Message,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as db:
        existing = await get_own_account(AccountRepository(db), message.from_user.id)
    if not existing:
        await message.answer("ابتدا ثبت‌نام کنید.", reply_markup=main_menu_keyboard())
        return

    referral = existing.referral_code or "-"
    await message.answer(
        f"🎁 کد معرف شما: <code>{referral}</code>\n"
        "می‌توانید این کد را به دوستانتان بدهید.",
        reply_markup=registered_menu_keyboard(),
        protect_content=True,
    )


@router.message(F.text == "🎁 کد معرف دارم")
async def ask_referral_code(message: Message, state: FSMContext) -> None:
    await state.set_state(RegistrationStates.waiting_referral_code)
    await message.answer(
        "🎁 کد معرف خود را وارد کنید:\n\n"
        f"{PRIVACY_SHORT}\n\n"
        "برای لغو: «❌ لغو ثبت‌نام»",
        reply_markup=main_menu_keyboard(),
    )


@router.message(F.text == "🚪 لغو ثبت‌نام")
async def start_unregister(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as db:
        existing = await get_own_account(AccountRepository(db), message.from_user.id)
    if not existing:
        await message.answer("شما ثبت‌نام نکرده‌اید.", reply_markup=main_menu_keyboard())
        return

    await state.set_state(UnregisterStates.waiting_confirm)
    await message.answer(UNREGISTER_WARNING, reply_markup=unregister_confirm_keyboard())


@router.message(UnregisterStates.waiting_confirm, F.text == "✅ بله، حذف شود")
async def confirm_unregister(
    message: Message,
    state: FSMContext,
    config: AppConfig,
    session_factory: async_sessionmaker[AsyncSession],
    service_context: ServiceContext | None = None,
) -> None:
    async with session_factory() as db:
        existing = await get_own_account(AccountRepository(db), message.from_user.id)
        if not existing:
            await state.clear()
            await message.answer("حسابی یافت نشد.", reply_markup=main_menu_keyboard())
            return

        pool = service_context.pool if service_context else None
        deleted = await delete_account(
            config,
            db,
            existing.id,
            pool=pool,
        )

    await state.clear()
    if deleted:
        await message.answer(
            "✅ ثبت‌نام شما لغو شد.\n"
            "سشن از سرور حذف و مانیتورینگ متوقف شد.\n\n"
            f"{PRIVACY_SHORT}",
            reply_markup=main_menu_keyboard(),
        )
    else:
        await message.answer(
            "خطا در حذف حساب. لطفاً با ادمین تماس بگیرید.",
            reply_markup=main_menu_keyboard(),
        )


@router.message(UnregisterStates.waiting_confirm, F.text == "❌ خیر، انصراف")
async def cancel_unregister(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("عملیات لغو شد.", reply_markup=registered_menu_keyboard())
