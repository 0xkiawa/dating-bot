from aiogram import types
from aiogram.types import InputMediaPhoto
from sqlalchemy.ext.asyncio import AsyncSession

from app.business.profile_service import (
    _get_or_create_blurred_file_id,
    _schedule_reblur_carousel,
    build_carousel_page,
)
from app.filters.kb_filter import PhotoRevealCallback
from app.routers import dating_router
from database.services import Profile
from database.services.photo_reveal import PhotoReveal
from database.services.profile_media import ProfileMedia


@dating_router.callback_query(PhotoRevealCallback.filter())
async def reveal_photo_handler(
    callback: types.CallbackQuery,
    callback_data: PhotoRevealCallback,
    session: AsyncSession,
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

    # Rebuild caption text (same pattern as send_profile_with_dist / nav handler)
    from database.services.search import haversine_distance

    viewer = await Profile.get(session, viewer_id)
    if viewer and viewer.is_shared_location and profile.is_shared_location:
        distance = haversine_distance(
            viewer.latitude, viewer.longitude, profile.latitude, profile.longitude
        )
        city = f"📍 {round(distance, 2)} km"
    else:
        city = profile.city
    caption_text = f"{profile.name}, {profile.age}, {city}\n{profile.description}"

    # Build nav-only keyboard (no reveal button - it's used up)
    _, _, nav_markup = await build_carousel_page(
        session=session,
        profile_id=profile.id,
        media_items=media_items,
        index=index,
        viewer_id=viewer_id,
        caption_text=caption_text,
    )

    # Show the REAL clear photo right now
    await callback.message.edit_media(
        media=InputMediaPhoto(media=media_obj.media, caption=f"{caption_text}{dots}"),
        reply_markup=nav_markup,
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
        delay_seconds=duration,
    )