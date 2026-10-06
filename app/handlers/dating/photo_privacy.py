from aiogram import F, types
from aiogram.filters import Command
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.business.menu_service import menu
from app.keyboards.default.registration_form import RegistrationFormKb
from app.routers import dating_router
from app.states.default import PhotoPrivacyEdit
from app.text import message_text as mt
from database.models.user import UserModel
from database.services.profile_media import ProfileMedia
from loader import _

PRIVACY_LABELS = {
    None: "🚫 No Blur",
    3: "⏱ 3s",
    5: "⏱ 5s",
    10: "⏱ 10s",
    30: "⏱ 30s",
}


@dating_router.message(StateFilter(None), Command("privacy"))
async def privacy_command(
    message: types.Message, state: FSMContext, user: UserModel, session: AsyncSession
) -> None:
    """Lets an existing user change their photo blur/reveal setting without recreating their profile."""
    if not user.profile:
        await message.answer(mt.NO_PROFILE_FOR_SEARCH)
        return

    photos = await ProfileMedia.get_profile_photos(session, user.id)
    if not photos:
        await message.answer("You don't have any photos uploaded yet.")
        return

    current_values = {p.reveal_duration for p in photos}
    if len(current_values) == 1:
        current_label = PRIVACY_LABELS.get(next(iter(current_values)), "Unknown")
        current_text = f"Current setting: <b>{current_label}</b>"
    else:
        current_text = "Your photos currently have mixed settings."

    await state.set_state(PhotoPrivacyEdit.selecting)
    kb = RegistrationFormKb.photo_privacy()
    await message.answer(
        text=f"{mt.PHOTO_PRIVACY_PROMPT}\n{current_text}",
        reply_markup=kb,
    )


@dating_router.message(StateFilter(PhotoPrivacyEdit.selecting), F.text)
async def privacy_selection_handler(
    message: types.Message, state: FSMContext, user: UserModel, session: AsyncSession
) -> None:
    privacy_map = {
        _("🚫 No Blur"): None,
        _("⏱ 3s"): 3,
        _("⏱ 5s"): 5,
        _("⏱ 10s"): 10,
        _("⏱ 30s"): 30,
    }

    if message.text not in privacy_map:
        await message.answer(mt.INVALID_OPTION)
        return

    reveal_duration = privacy_map[message.text]

    photos = await ProfileMedia.get_profile_photos(session, user.id)
    for photo in photos:
        photo.reveal_duration = reveal_duration
    await session.commit()

    await state.clear()

    label = PRIVACY_LABELS.get(reveal_duration, "Unknown")
    await message.answer(f"✅ Photo privacy updated to: <b>{label}</b>")
    await menu(chat_id=user.id)