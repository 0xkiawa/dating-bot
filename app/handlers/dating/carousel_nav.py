from aiogram import types
from aiogram.types import InputMediaPhoto
from sqlalchemy.ext.asyncio import AsyncSession

from app.business.profile_service import build_carousel_page
from app.filters.kb_filter import CarouselNavCallback
from app.routers import dating_router
from database.models.user import UserModel
from database.services import Profile
from database.services.profile_media import ProfileMedia
from database.services.search import haversine_distance


@dating_router.callback_query(CarouselNavCallback.filter())
async def carousel_nav_handler(
    callback: types.CallbackQuery,
    callback_data: CarouselNavCallback,
    user: UserModel,
    session: AsyncSession,
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

    # Rebuild the same caption text used in send_profile_with_dist
    if user.profile.is_shared_location and profile.is_shared_location:
        distance = haversine_distance(
            user.profile.latitude, user.profile.longitude, profile.latitude, profile.longitude
        )
        city = f"📍 {round(distance, 2)} km"
    else:
        city = profile.city
    text = f"{profile.name}, {profile.age}, {city}\n{profile.description}"

    photo_id, caption, markup = await build_carousel_page(
        session=session,
        profile_id=profile.id,
        media_items=media_items,
        index=callback_data.index,
        viewer_id=callback.from_user.id,
        caption_text=text,
    )

    await callback.message.edit_media(
        media=InputMediaPhoto(media=photo_id, caption=caption),
        reply_markup=markup,
    )
    await callback.answer()