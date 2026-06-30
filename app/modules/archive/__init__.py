from app.core.module_api import BotModule, MenuButton
from app.modules.archive import bot, events, jobs, migrations, models  # noqa: F401

MODULE = BotModule(
    name="archive",
    order=10,
    routers=[bot.router],
    menu_buttons=[
        MenuButton(text="🗑 پیام‌های حذف شده", section="registered", order=10),
    ],
    register_events=events.register_events,
    register_jobs=jobs.register_jobs,
    light_migrations=migrations.light_migrations,
)
