from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove

from app.core.loader import get_modules
from app.core.module_api import MenuSection


def _buttons_for_section(section: MenuSection) -> list[str]:
    buttons: list[tuple[int, str]] = []
    for module in get_modules():
        for btn in module.menu_buttons:
            if btn.section == section:
                buttons.append((btn.order, btn.text))
    buttons.sort(key=lambda item: (item[0], item[1]))
    return [text for _, text in buttons]


def _build_keyboard(texts: list[str], *, columns: int = 1) -> ReplyKeyboardMarkup:
    rows: list[list[KeyboardButton]] = []
    row: list[KeyboardButton] = []
    for text in texts:
        row.append(KeyboardButton(text=text))
        if len(row) >= columns:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    texts = _buttons_for_section("main")
    if not texts:
        texts = ["📝 ثبت‌نام", "🎁 کد معرف دارم"]
    return _build_keyboard(texts)


def registered_menu_keyboard() -> ReplyKeyboardMarkup:
    texts = _buttons_for_section("registered")
    if not texts:
        texts = [
            "🗑 پیام‌های حذف شده",
            "🔍 شناسایی پیام ناشناس",
            "🎁 کد معرف من",
            "🚪 لغو ثبت‌نام",
        ]
    return _build_keyboard(texts)


def admin_menu_keyboard() -> ReplyKeyboardMarkup:
    texts = _buttons_for_section("admin")
    if not texts:
        texts = [
            "📊 آمار سرویس",
            "👥 لیست کاربران",
            "🔍 جزئیات کاربر",
            "🗑 حذف کاربر",
            "📈 فعالیت اخیر",
            "🔙 خروج از پنل",
        ]
    return _build_keyboard(texts, columns=2)


def unregister_confirm_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ بله، حذف شود")],
            [KeyboardButton(text="❌ خیر، انصراف")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def deleted_messages_nav_keyboard(*, has_prev: bool, has_next: bool) -> ReplyKeyboardMarkup:
    rows: list[list[KeyboardButton]] = []
    nav_row: list[KeyboardButton] = []
    if has_prev:
        nav_row.append(KeyboardButton(text="◀️ قبلی"))
    if has_next:
        nav_row.append(KeyboardButton(text="▶️ بعدی"))
    if nav_row:
        rows.append(nav_row)
    rows.append([KeyboardButton(text="🔙 بازگشت")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def share_phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 اشتراک شماره تماس", request_contact=True)],
            [KeyboardButton(text="❌ لغو ثبت‌نام")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def code_entry_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="1"),
                KeyboardButton(text="2"),
                KeyboardButton(text="3"),
            ],
            [
                KeyboardButton(text="4"),
                KeyboardButton(text="5"),
                KeyboardButton(text="6"),
            ],
            [
                KeyboardButton(text="7"),
                KeyboardButton(text="8"),
                KeyboardButton(text="9"),
            ],
            [
                KeyboardButton(text="⌫"),
                KeyboardButton(text="0"),
                KeyboardButton(text="✅"),
            ],
            [KeyboardButton(text="❌ لغو ثبت‌نام")],
        ],
        resize_keyboard=True,
        input_field_placeholder="فقط از دکمه‌ها استفاده کنید",
    )


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()
