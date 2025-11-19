from typing import Any, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

from app.business.alert_service import new_user_alert_to_group
from app.constans import REFERAL_SOURCES
from database.models.user import UserStatus
from database.services import User
from database.services.profile import Profile
from database.services.referal import Referal
from utils.base62 import decode_base62
from utils.logging import logger  # ADD THIS IMPORT


class CommonMiddleware(BaseMiddleware):
    async def __call__(
        self, handler: Callable, message: Message | CallbackQuery, data: dict
    ) -> Any:
        session = data["session"]

        user, is_create = await User.get_or_create(
            session=session,
            id=message.from_user.id,
            username=message.from_user.username,
            language=message.from_user.language_code,
        )

        if user.status == UserStatus.Banned:
            return

        if isinstance(message, Message) and is_create:
            code = "unk"
            try:
                if inviter_code := getattr(data.get("command"), "args", None):
                    logger.log("DATABASE", f"Processing invite code: {inviter_code}")  # ADD THIS
                    code, inviter_id = inviter_code.split("_")
                    inviter_id = decode_base62(inviter_id)
                    logger.log("DATABASE", f"Decoded inviter ID: {inviter_id}")  # ADD THIS
                    
                    if await User.get_by_id(session, inviter_id):
                        logger.log("DATABASE", f"Creating referral: user={user.id}, inviter={inviter_id}")  # ADD THIS
                        await Referal.create(
                            session=session,
                            user_id=user.id,
                            inviter_id=inviter_id,
                            code=code,
                            source=REFERAL_SOURCES.get(code, "Unknown"),  # CHANGED: Use .get() to avoid KeyError
                        )
                        logger.log("DATABASE", f"✅ Referral created successfully!")  # ADD THIS
                    else:
                        logger.log("DATABASE", f"⚠️ Inviter {inviter_id} not found in database")  # ADD THIS
            except Exception as e:
                logger.log("DATABASE", f"❌ Error creating referral: {e}")  # CHANGED: Show the actual error
            
            await new_user_alert_to_group(user=user, code=code)

            if user.profile and not user.profile.is_active:
                await Profile.update(
                    session=session,
                    id=user.id,
                    is_active=True,
                )

        data["user"] = user
        return await handler(message, data)