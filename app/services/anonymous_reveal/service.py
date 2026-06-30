from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from telethon import TelegramClient
from telethon.errors import (
    ChannelPrivateError,
    FloodWaitError,
    RPCError,
    UsernameInvalidError,
    UsernameNotOccupiedError,
)

from app.services.anonymous_reveal.bot_scanner import (
    DEFAULT_MAX_MESSAGES,
    ScanProgressCallback,
    normalize_bot_username,
    scan_all_sender_ids,
)
from app.services.anonymous_reveal.models import RevealBatchResult, RevealResult
from app.services.anonymous_reveal.usinfo_lookup import lookup_user_by_id
from app.telegram.client_utils import ensure_client_connected

logger = logging.getLogger(__name__)

LOOKUP_DELAY_SECONDS = 0.6

LookupProgressCallback = Callable[[int, int, int], Awaitable[None]]


class AnonymousRevealError(Exception):
    """Base error for anonymous reveal flow."""


class TargetBotNotFound(AnonymousRevealError):
    pass


class NoCallbackUserIdFound(AnonymousRevealError):
    pass


class UsInfoLookupFailed(AnonymousRevealError):
    pass


class RevealRateLimited(AnonymousRevealError):
    pass


class RevealService:
    async def reveal_all_anonymous_senders(
        self,
        client: TelegramClient,
        bot_username: str,
        *,
        max_messages: int = DEFAULT_MAX_MESSAGES,
        on_scan_progress: ScanProgressCallback | None = None,
        on_lookup_progress: LookupProgressCallback | None = None,
    ) -> RevealBatchResult:
        try:
            normalized = normalize_bot_username(bot_username)
        except ValueError as exc:
            raise TargetBotNotFound(str(exc)) from exc

        await ensure_client_connected(client)

        try:
            scan_results, messages_scanned, hit_limit = await scan_all_sender_ids(
                client,
                normalized,
                max_messages=max_messages,
                on_progress=on_scan_progress,
            )
        except FloodWaitError as exc:
            raise RevealRateLimited(
                f"تلگرام محدودیت موقت گذاشته. {exc.seconds} ثانیه بعد دوباره تلاش کنید."
            ) from exc
        except (UsernameInvalidError, UsernameNotOccupiedError) as exc:
            raise TargetBotNotFound(f"ربات @{normalized} پیدا نشد.") from exc
        except (ChannelPrivateError, ValueError) as exc:
            raise TargetBotNotFound(f"ربات @{normalized} پیدا نشد.") from exc
        except RPCError as exc:
            logger.warning("RPC error scanning @%s: %s", normalized, exc)
            raise TargetBotNotFound(f"دسترسی به ربات @{normalized} ممکن نیست.") from exc

        if not scan_results:
            scope = f"آخرین {messages_scanned} پیام" if hit_limit else "کل تاریخچه چت"
            raise NoCallbackUserIdFound(
                f"در {scope} @{normalized} دکمه‌ای با آیدی کاربر یافت نشد."
            )

        entries: list[RevealResult] = []
        total = len(scan_results)
        for index, scan_result in enumerate(scan_results):
            if on_lookup_progress:
                await on_lookup_progress(index + 1, total, scan_result.user_id)

            if index > 0:
                await asyncio.sleep(LOOKUP_DELAY_SECONDS)

            try:
                lookup = await lookup_user_by_id(client, scan_result.user_id)
                entries.append(
                    RevealResult(
                        bot_username=normalized,
                        message_id=scan_result.message_id,
                        button_text=scan_result.button_text,
                        decoded_callback=scan_result.decoded_callback,
                        user_id=scan_result.user_id,
                        username=lookup.username,
                        display_name=lookup.display_name,
                        phone=lookup.phone,
                        lookup_failed=False,
                    )
                )
            except FloodWaitError as exc:
                raise RevealRateLimited(
                    f"تلگرام محدودیت موقت گذاشته. {exc.seconds} ثانیه بعد دوباره تلاش کنید."
                ) from exc
            except Exception:
                logger.exception("usinfobot lookup failed for user_id=%s", scan_result.user_id)
                entries.append(
                    RevealResult(
                        bot_username=normalized,
                        message_id=scan_result.message_id,
                        button_text=scan_result.button_text,
                        decoded_callback=scan_result.decoded_callback,
                        user_id=scan_result.user_id,
                        username=None,
                        display_name=None,
                        phone=None,
                        lookup_failed=True,
                    )
                )

        return RevealBatchResult(
            bot_username=normalized,
            entries=entries,
            messages_scanned=messages_scanned,
            buttons_found=len(scan_results),
            scan_limited=hit_limit,
        )

    async def reveal_latest_anonymous_sender(
        self,
        client: TelegramClient,
        bot_username: str,
    ) -> RevealResult:
        batch = await self.reveal_all_anonymous_senders(client, bot_username)
        return batch.entries[0]
