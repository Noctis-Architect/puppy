from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 ثبت‌نام")],
            [KeyboardButton(text="🎁 کد معرف دارم")],
        ],
        resize_keyboard=True,
    )


def registered_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🗑 پیام‌های حذف شده")],
            [KeyboardButton(text="🔍 شناسایی پیام ناشناس")],
            [KeyboardButton(text="🎁 کد معرف من")],
            [KeyboardButton(text="🚪 لغو ثبت‌نام")],
        ],
        resize_keyboard=True,
    )


def unregister_confirm_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ بله، حذف شود")],
            [KeyboardButton(text="❌ خیر، انصراف")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def admin_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📊 آمار سرویس"),
                KeyboardButton(text="👥 لیست کاربران"),
            ],
            [
                KeyboardButton(text="🔍 جزئیات کاربر"),
                KeyboardButton(text="🗑 حذف کاربر"),
            ],
            [KeyboardButton(text="📈 فعالیت اخیر")],
            [KeyboardButton(text="🔙 خروج از پنل")],
        ],
        resize_keyboard=True,
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
