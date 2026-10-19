from typing import Any, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

from app.business.alert_service import new_user_alert_to_group
from app.locales import normalize_locale
from app.constans import REFERAL_SOURCES
from app.consent import require_consent
from database.models.user import UserStatus
from database.services import User
from database.services.profile import Profile
from database.services.referal import Referal
from database.services.share import (
    get_share_start_payload,
    resolve_share_slug,
    save_pending_shared_view,
)
from utils.base62 import decode_base62
from utils.logging import logger  # ADD THIS IMPORT


class CommonMiddleware(BaseMiddleware):
    async def __call__(
        self, handler: Callable, message: Message | CallbackQuery, data: dict
    ) -> Any:
        session = data["session"]

        user = data.get("user")
        if user is None:
            user, is_create = await User.get_or_create(
                session=session,
                id=message.from_user.id,
                username=message.from_user.username,
                language=normalize_locale(message.from_user.language_code),
            )
        else:
            is_create = False

        if user.status == UserStatus.Banned:
            return

        if isinstance(message, Message) and is_create:
            code = "unk"
            try:
                if (
                    (inviter_code := getattr(data.get("command"), "args", None))
                    and inviter_code.startswith("usr_")
                ):
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

        if isinstance(message, Message):
            share_payload = get_share_start_payload(message.text)
            if share_payload:
                target = await resolve_share_slug(session, share_payload)
                if target and target.id != user.id:
                    await save_pending_shared_view(session, user.id, target.id)

        data["user"] = user
        if not data.get("consent_gate_checked") and not await require_consent(message, user):
            return
        return await handler(message, data)
