from app.core.module_api import BotModule
from app.modules.contact_tracking import events, jobs, models  # noqa: F401

MODULE = BotModule(
    name="contact_tracking",
    order=40,
    register_events=events.register_events,
    register_jobs=jobs.register_jobs,
)
