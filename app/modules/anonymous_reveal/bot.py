from __future__ import annotations

import asyncio
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.access import get_own_account
from app.bot.concurrency import account_client_lock
from app.bot.keyboards import registered_menu_keyboard
from app.bot.service_context import ServiceContext
from app.modules.anonymous_reveal.states import AnonymousRevealStates
from app.repositories.account_repo import AccountRepository
from app.services.anonymous_reveal.bot_scanner import DEFAULT_MAX_MESSAGES
from app.services.anonymous_reveal.models import RevealBatchResult, RevealResult
from app.services.anonymous_reveal.service import (
    AnonymousRevealError,
    NoCallbackUserIdFound,
    RevealRateLimited,
    RevealService,
    TargetBotNotFound,
)
from app.telegram.client_utils import SessionExpiredError, ensure_client_connected

router = Router()
logger = logging.getLogger(__name__)

MENU_BUTTON = "🔍 شناسایی پیام ناشناس"
BACK_BUTTON = "🔙 بازگشت"
MAX_MESSAGE_LENGTH = 4000
HEARTBEAT_SECONDS = 4

def _is_other_menu_button(message: Message) -> bool:
    """True for any module menu button (except this one) so we don't treat it as a bot username."""
    text = (message.text or "").strip()
    if not text or text == MENU_BUTTON:
        return False

    from app.core.loader import get_modules

    for module in get_modules():
        for btn in module.menu_buttons:
            if btn.section in ("registered", "main", "admin") and btn.text == text:
                return True
    return False


_reveal_service = RevealService()


def _format_entry(index: int, entry: RevealResult) -> str:
    lines = [f"<b>{index}.</b> 🆔 <code>{entry.user_id}</code>"]
    if entry.lookup_failed:
        lines.append("   ⚠️ usinfobot: ناموفق")
    elif entry.username:
        lines.append(f"   👤 @{entry.username}")
    else:
        lines.append("   👤 (یوزرنیم عمومی ندارد)")
    if entry.display_name:
        lines.append(f"   📛 {entry.display_name}")
    if entry.phone:
        lines.append(f"   📱 {entry.phone}")
    elif not entry.lookup_failed:
        lines.append("   📱 (در دسترس نیست)")
    lines.append(f"   🔘 {entry.button_text or '-'}")
    lines.append(f"   📎 <code>{entry.decoded_callback}</code>")
    return "\n".join(lines)


def _format_batch_result(result: RevealBatchResult) -> list[str]:
    limit_note = (
        f"\n⚠️ فقط آخرین {DEFAULT_MAX_MESSAGES} پیام اسکن شد."
        if result.scan_limited
        else ""
    )
    header = (
        "🔍 <b>نتیجه شناسایی</b>\n\n"
        f"🤖 ربات: @{result.bot_username}\n"
        f"📊 پیام‌های اسکن‌شده: {result.messages_scanned} | "
        f"فرستنده‌های یافت‌شده: {result.buttons_found}"
        f"{limit_note}\n"
    )

    chunks: list[str] = []
    current = header
    for index, entry in enumerate(result.entries, start=1):
        block = _format_entry(index, entry) + "\n\n"
        if len(current) + len(block) > MAX_MESSAGE_LENGTH:
            chunks.append(current.rstrip())
            current = f"🔍 <b>ادامه نتایج</b>\n\n{block}"
        else:
            current += block

    if current.strip():
        chunks.append(current.rstrip())
    return chunks or [header + "\nهیچ نتیجه‌ای یافت نشد."]


async def _resolve_account(
    message: Message,
    session_factory: async_sessionmaker[AsyncSession],
    service_context: ServiceContext | None,
):
    async with session_factory() as db:
        account = await get_own_account(AccountRepository(db), message.from_user.id)

    if not account:
        return None, "ابتدا ثبت‌نام کنید."

    if service_context is None or account.id not in service_context.pool.clients:
        return None, "اتصال اکانت شما فعال نیست. لطفاً چند لحظه صبر کنید یا سرویس را ری‌استارت کنید."

    managed = service_context.pool.clients[account.id]
    try:
        await ensure_client_connected(managed.client)
    except SessionExpiredError:
        return None, "سشن تلگرام شما منقضی شده. لطفاً «🚪 لغو ثبت‌نام» بزنید و دوباره ثبت‌نام کنید."
    except (ConnectionError, OSError):
        return None, "اتصال تلگرام قطع شده. چند لحظه صبر کنید و دوباره تلاش کنید."

    return account, None


@router.message(F.text == MENU_BUTTON)
async def start_anonymous_reveal(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker[AsyncSession],
    service_context: ServiceContext | None = None,
) -> None:
    account, error = await _resolve_account(message, session_factory, service_context)
    if error:
        await message.answer(
            error,
            reply_markup=registered_menu_keyboard() if account else None,
        )
        return

    await state.set_state(AnonymousRevealStates.waiting_bot_username)
    await message.answer(
        "یوزرنیم ربات ناشناس را ارسال کنید.\n"
        "مثال: <code>@XBCHATBOT</code> یا <code>XBCHATBOT</code>\n\n"
        f"آخرین {DEFAULT_MAX_MESSAGES} پیام چت اسکن می‌شود.\n"
        f"برای انصراف «{BACK_BUTTON}» را بزنید.",
        reply_markup=registered_menu_keyboard(),
    )


@router.message(AnonymousRevealStates.waiting_bot_username, F.text == BACK_BUTTON)
async def cancel_anonymous_reveal(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("بازگشت به منو.", reply_markup=registered_menu_keyboard())


@router.message(AnonymousRevealStates.waiting_bot_username, _is_other_menu_button)
async def ignore_menu_while_waiting(message: Message) -> None:
    await message.answer(
        "لطفاً یوزرنیم ربات ناشناس را ارسال کنید یا «🔙 بازگشت» را بزنید.",
        reply_markup=registered_menu_keyboard(),
    )


@router.message(AnonymousRevealStates.waiting_bot_username)
async def process_bot_username(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker[AsyncSession],
    service_context: ServiceContext | None = None,
) -> None:
    if not message.text:
        await message.answer("لطفاً یوزرنیم ربات را به صورت متن ارسال کنید.")
        return

    account, error = await _resolve_account(message, session_factory, service_context)
    if error:
        await state.clear()
        await message.answer(error, reply_markup=registered_menu_keyboard())
        return

    bot_username = message.text.strip()
    progress = await message.answer(
        "⏳ در حال آماده‌سازی…\n"
        "📨 ۰ پیام | 👤 ۰ فرستنده"
    )
    managed = service_context.pool.clients[account.id]
    progress_state = {"scanned": 0, "found": 0, "status": "در حال آماده‌سازی…"}
    heartbeat_stop = asyncio.Event()

    async def _render_progress() -> None:
        try:
            await progress.edit_text(
                f"⏳ {progress_state['status']}\n"
                f"📨 {progress_state['scanned']} پیام | 👤 {progress_state['found']} فرستنده\n"
                "⏱️ تلگرام گاهی ۲۰–۳۰ ثانیه صبر می‌کند — عادی است."
            )
        except Exception:
            logger.debug("Could not update reveal progress message", exc_info=True)

    async def _heartbeat() -> None:
        while not heartbeat_stop.is_set():
            try:
                await asyncio.wait_for(heartbeat_stop.wait(), timeout=HEARTBEAT_SECONDS)
                return
            except asyncio.TimeoutError:
                await _render_progress()

    async def on_scan_progress(scanned: int, found: int, hit_limit: bool, status: str) -> None:
        progress_state["scanned"] = scanned
        progress_state["found"] = found
        if hit_limit and scanned >= DEFAULT_MAX_MESSAGES:
            progress_state["status"] = f"{status} (حداکثر {DEFAULT_MAX_MESSAGES} پیام)"
        else:
            progress_state["status"] = status
        await _render_progress()

    async def on_lookup_progress(current: int, total: int, user_id: int) -> None:
        progress_state["status"] = f"usinfobot — {current} از {total}"
        await _render_progress()

    heartbeat_task = asyncio.create_task(_heartbeat())

    try:
        async with account_client_lock(account.id):
            batch = await _reveal_service.reveal_all_anonymous_senders(
                managed.client,
                bot_username,
                on_scan_progress=on_scan_progress,
                on_lookup_progress=on_lookup_progress,
            )
    except TargetBotNotFound as exc:
        await progress.edit_text(f"❌ {exc}")
        return
    except NoCallbackUserIdFound as exc:
        await progress.edit_text(f"❌ {exc}")
        return
    except RevealRateLimited as exc:
        await progress.edit_text(f"⏳ {exc}")
        return
    except SessionExpiredError:
        await progress.edit_text(
            "❌ سشن تلگرام شما منقضی شده. «🚪 لغو ثبت‌نام» بزنید و دوباره ثبت‌نام کنید."
        )
        return
    except (ConnectionError, OSError):
        await progress.edit_text(
            "❌ اتصال تلگرام قطع شد. چند لحظه صبر کنید و دوباره تلاش کنید."
        )
        return
    except AnonymousRevealError as exc:
        await progress.edit_text(f"❌ {exc}")
        return
    except Exception:
        logger.exception("Anonymous reveal failed for account=%s", account.id)
        await progress.edit_text("❌ خطای غیرمنتظره رخ داد. دوباره تلاش کنید.")
        return
    finally:
        heartbeat_stop.set()
        heartbeat_task.cancel()
        await state.clear()

    chunks = _format_batch_result(batch)
    try:
        await progress.edit_text(chunks[0])
    except Exception:
        await message.answer(chunks[0], protect_content=True)

    for chunk in chunks[1:]:
        await message.answer(chunk, protect_content=True)

    await message.answer(
        f"✅ شناسایی انجام شد — {len(batch.entries)} فرستنده.",
        reply_markup=registered_menu_keyboard(),
    )
