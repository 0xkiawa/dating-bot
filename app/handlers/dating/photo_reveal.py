from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.types import InputMediaPhoto
from sqlalchemy.ext.asyncio import AsyncSession

from app.business.profile_service import (
    _get_or_create_blurred_file_id,
    _schedule_reblur_carousel,
    build_carousel_page,
    build_profile_caption,
)
from app.filters.kb_filter import PhotoRevealCallback
from app.routers import dating_router
from app.states.default import Search
from database.services import Profile
from database.services.photo_reveal import PhotoReveal
from database.services.profile_media import ProfileMedia


@dating_router.callback_query(PhotoRevealCallback.filter())
async def reveal_photo_handler(
    callback: types.CallbackQuery,
    callback_data: PhotoRevealCallback,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """
    One-time photo reveal, within the carousel. Once used, this viewer can NEVER
    reveal this specific photo again - no matter what happens between them afterward.
    """
    media_id = callback_data.media_id
    viewer_id = callback.from_user.id

    already = await PhotoReveal.has_revealed(session, media_id, viewer_id)
    if already:
        await callback.answer("You've already used your one-time reveal on this photo.", show_alert=True)
        return

    media_obj = await ProfileMedia.get_by_id(session, media_id)
    if not media_obj:
        await callback.answer("Photo not found.", show_alert=True)
        return

    is_new = await PhotoReveal.mark_revealed(session, media_id, viewer_id)
    if not is_new:
        await callback.answer("You've already used your one-time reveal on this photo.", show_alert=True)
        return

    # Figure out where this photo sits in the carousel so nav buttons stay correct
    profile = await Profile.get(session, media_obj.profile_id)
    media_items = await ProfileMedia.get_profile_photos(session=session, profile_id=profile.id)
    index = next((i for i, m in enumerate(media_items) if m.id == media_obj.id), 0)
    total = len(media_items)
    dots = "\n" + "".join("●" if i == index else "○" for i in range(total)) if total > 1 else ""

    viewer = await Profile.get(session, viewer_id)
    search_active = await state.get_state() in {
        Search.search.state,
        Search.message.state,
    }
    state_data = await state.get_data()
    caption_text = build_profile_caption(
        viewer,
        profile,
        mode=state_data.get("current_mode"),
        include_reasons=search_active,
        caption_limit=True,
    )

    # Build nav-only keyboard (no reveal button - it's used up)
    _, _, nav_markup = await build_carousel_page(
        session=session,
        profile_id=profile.id,
        media_items=media_items,
        index=index,
        viewer_id=viewer_id,
        caption_text=caption_text,
        include_actions=search_active,
    )
    nav_only_markup = nav_markup
    if search_active:
        _, _, nav_only_markup = await build_carousel_page(
            session=session,
            profile_id=profile.id,
            media_items=media_items,
            index=index,
            viewer_id=viewer_id,
            caption_text=caption_text,
            include_actions=False,
        )

    # Show the REAL clear photo right now
    await callback.message.edit_media(
        media=InputMediaPhoto(media=media_obj.media, caption=f"{caption_text}{dots}"),
        reply_markup=nav_markup,
    )
    if search_active:
        await state.update_data(
            active_card_chat_id=callback.message.chat.id,
            active_card_message_id=callback.message.message_id,
        )
    await callback.answer("👁 Revealed! This will blur again shortly.")

    # Schedule automatic re-blur after the owner's chosen duration
    blurred_id = await _get_or_create_blurred_file_id(session, media_obj, callback.message.chat.id)
    duration = media_obj.reveal_duration if media_obj.reveal_duration is not None else 2
    await _schedule_reblur_carousel(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        blurred_file_id=blurred_id,
        caption_with_dots=f"{caption_text}{dots}",
        nav_markup=nav_markup,
        nav_only_markup=nav_only_markup,
        delay_seconds=duration,
        state=state,
        profile_id=profile.id,
    )
