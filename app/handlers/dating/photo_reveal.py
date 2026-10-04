from aiogram import types
from aiogram.types import InputMediaPhoto
from sqlalchemy.ext.asyncio import AsyncSession

from app.business.profile_service import _get_or_create_blurred_file_id, _schedule_reblur
from app.filters.kb_filter import PhotoRevealCallback
from app.routers import dating_router
from database.services.photo_reveal import PhotoReveal
from database.services.profile_media import ProfileMedia


@dating_router.callback_query(PhotoRevealCallback.filter())
async def reveal_photo_handler(
    callback: types.CallbackQuery,
    callback_data: PhotoRevealCallback,
    session: AsyncSession,
) -> None:
    """
    One-time photo reveal. Once used, this viewer can NEVER reveal this
    specific photo again - no matter what happens between them afterward.
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
        # Someone double-tapped at the exact same moment - race condition guard
        await callback.answer("You've already used your one-time reveal on this photo.", show_alert=True)
        return

    # Swap to the real, clear photo and remove the button - no second chances
    await callback.message.edit_media(
        media=InputMediaPhoto(media=media_obj.media)
    )
    await callback.answer("👁 Revealed! This will blur again shortly.")

    # Schedule the automatic re-blur after the owner's chosen duration
    blurred_id = await _get_or_create_blurred_file_id(session, media_obj, callback.message.chat.id)
    duration = media_obj.reveal_duration if media_obj.reveal_duration is not None else 2
    await _schedule_reblur(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        blurred_file_id=blurred_id,
        delay_seconds=duration,
    )