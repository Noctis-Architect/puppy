from app.core.module_api import BotModule, MenuButton
from app.modules.group_tools import bot, events

MODULE = BotModule(
    name="group_tools",
    order=25,
    routers=[bot.router],
    menu_buttons=[
        MenuButton(text="👁 ردیابی فرد", section="registered", order=30),
        MenuButton(text="👥 گروه‌های تحت‌نظر", section="registered", order=40),
    ],
    register_events=events.register_events,
)
