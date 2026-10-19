from datetime import UTC, datetime

from aiogram import F, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.business.menu_service import menu
from app.handlers.common.share import deliver_pending_share_to_existing_member
from app.consent import CURRENT_CONSENT_VERSION, send_policy
from app.keyboards.inline.menus import welcome_menu_ikb
from app.routers import common_router
from app.text import message_text as mt
from data.config import LOGO_DIR
from database.models.user import UserModel
from database.services.share import get_pending_shared_view
from loader import bot


@common_router.callback_query(F.data == "consent:terms")
async def show_terms(callback: types.CallbackQuery) -> None:
    await send_policy(callback, "terms")


@common_router.callback_query(F.data == "consent:privacy")
async def show_privacy_policy(callback: types.CallbackQuery) -> None:
    await send_policy(callback, "privacy")


@common_router.callback_query(F.data == "consent:agree")
async def accept_consent(
    callback: types.CallbackQuery,
    user: UserModel,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    user.consent_version = CURRENT_CONSENT_VERSION
    user.consented_at = datetime.now(UTC)
    await session.commit()
    await callback.answer("Consent recorded.")

    if isinstance(callback.message, types.Message):
        await callback.message.edit_reply_markup(reply_markup=None)

    # Preserve an in-progress flow if a returning user encountered a version
    # update while they were already using the bot.
    if user.profile and await deliver_pending_share_to_existing_member(
        user=user, state=state, session=session
    ):
        return

    if await state.get_state():
        await bot.send_message(
            chat_id=callback.from_user.id,
            text="✅ Consent saved. You can continue where you left off.",
        )
    elif user.profile:
        await menu(user.id)
    else:
        photo = types.FSInputFile(LOGO_DIR)
        pending = await get_pending_shared_view(session, user.id)
        teaser = (
            "\n\nA CONQUEER member shared their profile with you. Create yours to see them."
            if pending
            else ""
        )
        await bot.send_photo(
            chat_id=callback.from_user.id,
            photo=photo,
            caption=mt.WELCOME + teaser,
            reply_markup=welcome_menu_ikb(),
        )
