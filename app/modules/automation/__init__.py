from app.core.module_api import BotModule, MenuButton
from app.modules.automation import bot, events, jobs, models  # noqa: F401

MODULE = BotModule(
    name="automation",
    order=60,
    routers=[bot.router],
    menu_buttons=[
        MenuButton(text="⏰ پیام زمان‌بندی", section="registered", order=70),
        MenuButton(text="🔔 یادآور", section="registered", order=75),
    ],
    register_events=events.register_events,
    register_jobs=jobs.register_jobs,
)
