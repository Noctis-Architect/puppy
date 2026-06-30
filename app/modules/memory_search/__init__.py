from app.core.module_api import BotModule, MenuButton
from app.modules.memory_search import bot, jobs

MODULE = BotModule(
    name="memory_search",
    order=50,
    routers=[bot.router],
    menu_buttons=[
        MenuButton(text="🔎 جستجو", section="registered", order=50),
        MenuButton(text="📋 پروفایل مخاطب", section="registered", order=55),
        MenuButton(text="📤 اکسپورت مکالمه", section="registered", order=60),
    ],
    register_jobs=jobs.register_jobs,
)
