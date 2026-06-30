from app.core.module_api import BotModule
from app.modules.message_intel import events

MODULE = BotModule(
    name="message_intel",
    order=30,
    register_events=events.register_events,
)
