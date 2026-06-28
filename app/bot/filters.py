from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import Message

from app.config import AppConfig


class SuperAdminFilter(BaseFilter):
    async def __call__(self, message: Message, config: AppConfig) -> bool:
        return config.super_admin_id > 0 and message.from_user.id == config.super_admin_id
