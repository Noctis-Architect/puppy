from app.core.module_api import BotModule, MenuButton
from app.modules.anonymous_reveal import bot, events

MODULE = BotModule(
    name="anonymous_reveal",
    order=20,
    routers=[bot.router],
    menu_buttons=[
        MenuButton(text="🔍 شناسایی پیام ناشناس", section="registered", order=20),
    ],
    register_events=events.register_events,
)
