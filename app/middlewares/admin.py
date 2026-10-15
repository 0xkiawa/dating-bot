from typing import Any, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message

from app.consent import require_consent
from data.config import tgbot
from database.services import User


class AdminMiddleware(BaseMiddleware):
    async def __call__(self, handler: Callable, message: Message, data: dict) -> Any:
        session = data["session"]
        user = data.get("user")
        if user is None:
            user, _ = await User.get_or_create(
                session=session,
                id=message.from_user.id,
                username=message.from_user.username,
                language=message.from_user.language_code,
            )
        data["user"] = user
        if not data.get("consent_gate_checked") and not await require_consent(message, user):
            return
        if user.id in tgbot.ADMIN_IDS:
            return await handler(message, data)
