from app.core.module_api import BotModule, MenuButton
from app.modules.settings import bot, models  # noqa: F401

MODULE = BotModule(
    name="settings",
    order=15,
    routers=[bot.router],
    menu_buttons=[
        MenuButton(text="⚙️ تنظیمات", section="registered", order=80),
    ],
)
