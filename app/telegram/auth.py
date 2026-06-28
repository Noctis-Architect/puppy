from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import (
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    SessionPasswordNeededError,
)

from app.config import AppConfig
from app.db.models import Account
from app.repositories.account_repo import AccountRepository
from app.telegram.factory import connect_client
from app.telegram.session_paths import move_session_files, resolve_session_path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def ask_phone() -> str:
    phone = input("شماره تلفن (با کد کشور، مثلا +98912...): ").strip()
    return normalize_phone(phone)


def ask_code() -> str:
    return input("کد تأیید تلگرام: ").strip()


def ask_password() -> str:
    return input("رمز دو مرحله‌ای (2FA): ").strip()


def normalize_phone(phone: str) -> str:
    normalized = phone.strip().replace(" ", "").replace("-", "")
    if normalized.startswith("00"):
        normalized = "+" + normalized[2:]
    if not normalized.startswith("+"):
        if normalized.startswith("0"):
            normalized = "+98" + normalized[1:]
        elif normalized.startswith("98"):
            normalized = "+" + normalized
        else:
            normalized = "+" + normalized.lstrip("0")
    return normalized


@dataclass(slots=True)
class LoginResult:
    client: TelegramClient
    telegram_id: int
    phone: str
    username: str | None
    display_name: str | None


async def login_interactive(config: AppConfig, session_path: str) -> LoginResult:
    client = await connect_client(config, session_path)
    phone = ""

    if not await client.is_user_authorized():
        phone = ask_phone()
        sent = await client.send_code_request(phone)
        code = ask_code()
        try:
            await client.sign_in(phone, code, phone_code_hash=sent.phone_code_hash)
        except SessionPasswordNeededError:
            await client.sign_in(password=ask_password())

    me = await client.get_me()
    full_name = " ".join(part for part in (me.first_name, me.last_name) if part)
    return LoginResult(
        client=client,
        telegram_id=me.id,
        phone=me.phone or phone,
        username=me.username,
        display_name=full_name or None,
    )


async def request_login_code(
    config: AppConfig,
    session_path: str,
    phone: str,
) -> str:
    client = await connect_client(config, session_path)
    try:
        sent = await client.send_code_request(phone)
        return sent.phone_code_hash
    finally:
        await client.disconnect()


async def sign_in_with_code(
    config: AppConfig,
    session_path: str,
    *,
    phone: str,
    code: str,
    phone_code_hash: str,
    password: str | None = None,
) -> LoginResult:
    client = await connect_client(config, session_path)
    try:
        if not await client.is_user_authorized():
            try:
                await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
            except SessionPasswordNeededError:
                if not password:
                    raise
                await client.sign_in(password=password)

        me = await client.get_me()
        full_name = " ".join(part for part in (me.first_name, me.last_name) if part)
        return LoginResult(
            client=client,
            telegram_id=me.id,
            phone=me.phone or phone,
            username=me.username,
            display_name=full_name or None,
        )
    except Exception:
        await client.disconnect()
        raise


async def _reserved_session_names(db: AsyncSession) -> set[str]:
    result = await db.execute(select(Account.session_path))
    reserved: set[str] = set()
    for (session_path,) in result.all():
        reserved.add(Path(session_path).name)
    return reserved


async def _finalize_registration(
    config: AppConfig,
    db: AsyncSession,
    login: LoginResult,
    *,
    bot_chat_id: int | None = None,
    referred_by: str | None = None,
) -> Account:
    repo = AccountRepository(db)

    existing = await repo.get_by_telegram_id(login.telegram_id)
    if existing:
        await login.client.disconnect()
        raise ValueError(
            f"این اکانت قبلاً ثبت شده (id={existing.id}, phone={existing.phone})."
        )

    reserved = await _reserved_session_names(db)
    temp_path = Path(login.client.session.filename).with_suffix("")
    final_path = resolve_session_path(
        config.sessions_dir,
        username=login.username,
        telegram_id=login.telegram_id,
        reserved=reserved,
    )

    await login.client.disconnect()
    move_session_files(temp_path, final_path)

    account = await repo.create(
        telegram_id=login.telegram_id,
        phone=login.phone,
        username=login.username,
        session_path=str(final_path),
        display_name=login.display_name,
        bot_chat_id=bot_chat_id,
        referred_by=referred_by,
    )
    await db.commit()

    logger.info(
        "Registered account id=%s username=%s session=%s bot_chat_id=%s",
        account.id,
        account.username,
        final_path.name,
        bot_chat_id,
    )
    return account


async def register_account(
    config: AppConfig,
    db: AsyncSession,
) -> Account:
    config.sessions_dir.mkdir(parents=True, exist_ok=True)
    temp_path = config.sessions_dir / "_pending"
    login = await login_interactive(config, str(temp_path))

    account = await _finalize_registration(config, db, login)

    client = await connect_client(config, account.session_path)
    try:
        session_name = Path(account.session_path).name
        await client.send_message(
            "me",
            "✅ اکانت با موفقیت به سرویس Message Guard متصل شد.\n"
            f"📁 Session: session/{session_name}.session\n"
            "پیام‌های خصوصی ورودی ذخیره و حذف‌ها گزارش می‌شوند.",
        )
    finally:
        await client.disconnect()

    return account


async def register_account_via_bot(
    config: AppConfig,
    db: AsyncSession,
    *,
    session_path: str,
    phone: str,
    code: str,
    phone_code_hash: str,
    bot_chat_id: int,
    referred_by: str | None = None,
    password: str | None = None,
) -> Account:
    config.sessions_dir.mkdir(parents=True, exist_ok=True)
    normalized_phone = normalize_phone(phone)

    if referred_by:
        repo = AccountRepository(db)
        referrer = await repo.get_by_referral_code(referred_by)
        if not referrer:
            raise ValueError("کد معرف نامعتبر است.")

    login = await sign_in_with_code(
        config,
        session_path,
        phone=normalized_phone,
        code=code.strip(),
        phone_code_hash=phone_code_hash,
        password=password,
    )

    if login.telegram_id != bot_chat_id:
        await login.client.disconnect()
        raise ValueError("این شماره متعلق به اکانت تلگرام شما نیست.")

    return await _finalize_registration(
        config,
        db,
        login,
        bot_chat_id=bot_chat_id,
        referred_by=referred_by,
    )
