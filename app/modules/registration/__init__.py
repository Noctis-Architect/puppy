from app.core.module_api import BotModule, MenuButton
from app.modules.registration import bot

MODULE = BotModule(
    name="registration",
    order=5,
    routers=[bot.router],
    menu_buttons=[
        MenuButton(text="📝 ثبت‌نام", section="main", order=5),
        MenuButton(text="🎁 کد معرف دارم", section="main", order=10),
        MenuButton(text="🎁 کد معرف من", section="registered", order=90),
        MenuButton(text="🚪 لغو ثبت‌نام", section="registered", order=100),
    ],
)
