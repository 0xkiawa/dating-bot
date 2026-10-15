from typing import Any, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

from app.consent import require_consent
from database.models.user import UserStatus
from database.services import User


class DatingMiddleware(BaseMiddleware):
    async def __call__(
        self, handler: Callable, message: Message | CallbackQuery, data: dict
    ) -> Any:
        session = data["session"]
        user = data.get("user")
        if user is None:
            user, _ = await User.get_or_create(
                session,
                id=message.from_user.id,
                username=message.from_user.username,
                language=message.from_user.language_code,
            )
        if user.status == UserStatus.Banned and user.profile and user.profile.is_active:
            return

        data["user"] = user
        if not data.get("consent_gate_checked") and not await require_consent(message, user):
            return
        return await handler(message, data)
