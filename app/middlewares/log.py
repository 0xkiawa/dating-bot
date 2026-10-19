from typing import Any, Awaitable, Callable, Dict

from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.types import CallbackQuery, Message

from utils.logging import logger


class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        if isinstance(event, Message):
            logged_text = event.text
            if logged_text and logged_text.split(maxsplit=1)[0].split("@", 1)[0].lower() == "/start":
                logged_text = "/start [payload hidden]" if len(logged_text.split(maxsplit=1)) > 1 else "/start"
            logger.log(
                "MESSAGE", f"{event.from_user.id} ({event.from_user.username}): {logged_text}"
            )

        elif isinstance(event, CallbackQuery):
            logger.log(
                "CALLBACK", f"{event.from_user.id} ({event.from_user.username}): {event.data}"
            )

        return await handler(event, data)
