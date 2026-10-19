from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.types import InputMediaPhoto
from sqlalchemy.ext.asyncio import AsyncSession

from app.business.profile_service import build_carousel_page, build_profile_caption
from app.filters.kb_filter import CarouselNavCallback
from app.routers import dating_router
from app.states.default import Search
from database.models.user import UserModel
from database.services import Profile
from database.services.profile_media import ProfileMedia


@dating_router.callback_query(CarouselNavCallback.filter())
async def carousel_nav_handler(
    callback: types.CallbackQuery,
    callback_data: CarouselNavCallback,
    user: UserModel,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Handles ◀️/▶️ taps - edits the message in place to show the requested photo index."""
    profile = await Profile.get(session, callback_data.profile_id)
    if not profile:
        await callback.answer("Profile not found.", show_alert=True)
        return

    media_items = await ProfileMedia.get_profile_photos(session=session, profile_id=profile.id)
    if not media_items or callback_data.index >= len(media_items):
        await callback.answer()
        return

    search_active = await state.get_state() in {
        Search.search.state,
        Search.message.state,
    }
    state_data = await state.get_data()
    shared_card = state_data.get("shared_card_id") == profile.id
    card_mode = (
        state_data.get("shared_card_mode") if shared_card else state_data.get("current_mode")
    )
    mode_names = {"fun": "Fun", "dates": "Dating", "friends": "Friends"}
    mode_label = (
        mode_names.get(card_mode)
        if shared_card and card_mode != state_data.get("current_mode")
        else None
    )
    text = build_profile_caption(
        user.profile,
        profile,
        mode=card_mode,
        mode_label=mode_label,
        include_reasons=search_active,
        caption_limit=True,
    )

    photo_id, caption, markup = await build_carousel_page(
        session=session,
        profile_id=profile.id,
        media_items=media_items,
        index=callback_data.index,
        viewer_id=callback.from_user.id,
        caption_text=text,
        include_actions=search_active,
    )

    await callback.message.edit_media(
        media=InputMediaPhoto(media=photo_id, caption=caption),
        reply_markup=markup,
    )
    await callback.answer()
