from app.core.module_api import BotModule, MenuButton
from app.modules.admin import bot

MODULE = BotModule(
    name="admin",
    order=200,
    routers=[bot.router],
    menu_buttons=[
        MenuButton(text="📊 آمار سرویس", section="admin", order=10),
        MenuButton(text="👥 لیست کاربران", section="admin", order=20),
        MenuButton(text="🔍 جزئیات کاربر", section="admin", order=30),
        MenuButton(text="🗑 حذف کاربر", section="admin", order=40),
        MenuButton(text="📈 فعالیت اخیر", section="admin", order=50),
        MenuButton(text="🔙 خروج از پنل", section="admin", order=100),
    ],
)
