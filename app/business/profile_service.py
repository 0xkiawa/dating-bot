from io import BytesIO

from aiogram.types import BufferedInputFile, InputMediaPhoto
from aiogram.utils.keyboard import InlineKeyboardBuilder
from PIL import Image, ImageFilter
from sqlalchemy.ext.asyncio import AsyncSession

from app.filters.kb_filter import PhotoRevealCallback
from app.keyboards.inline.admin import block_user_ikb
from app.text import message_text as mt
from data.config import tgbot
from database.models.profile import ProfileModel
from database.models.profile_media import ProfileMediaModel
from database.models.user import UserModel
from database.services.complaint import Compleint
from database.services.photo_reveal import PhotoReveal
from database.services.profile_media import ProfileMedia
from database.services.search import haversine_distance
from loader import bot
from utils.logging import logger

MODERATOR_GROUP_ID = tgbot.MODERATOR_GROUP_ID

# Keep delayed re-blur tasks referenced so they aren't garbage collected mid-sleep
_pending_reblur_tasks = set()


async def send_profile(chat_id: int, profile: ProfileModel, session: AsyncSession) -> None:
    """Отправляет пользователю переданный в функцию профиль (unblurred - used for moderator review)"""
    media_items = await ProfileMedia.get_profile_photos(session=session, profile_id=profile.id)

    city = "📍 " + profile.city if profile.is_shared_location else profile.city
    text = f"{profile.name}, {profile.age}, {city}\n{profile.description}"

    media_list = []
    for i, media_obj in enumerate(media_items):
        if i == 0:
            media_list.append(InputMediaPhoto(media=media_obj.media, caption=text, parse_mode=None))
        else:
            media_list.append(InputMediaPhoto(media=media_obj.media))

    if media_list:
        await bot.send_media_group(chat_id=chat_id, media=media_list)
    else:
        await bot.send_message(chat_id=chat_id, text=text)


async def _get_or_create_blurred_file_id(
    session: AsyncSession, media_obj: ProfileMediaModel, viewer_chat_id: int
) -> str:
    """
    Returns a reusable Telegram file_id for the blurred version of this photo.
    Downloads + blurs + uploads only once per photo, then caches the file_id forever.
    """
    if media_obj.blurred_file_id:
        return media_obj.blurred_file_id

    # Download the original photo bytes from Telegram
    file = await bot.get_file(media_obj.media)
    file_bytes_io = BytesIO()
    await bot.download_file(file.file_path, destination=file_bytes_io)
    file_bytes_io.seek(0)

    # Blur it
    img = Image.open(file_bytes_io).convert("RGB")
    blurred = img.filter(ImageFilter.GaussianBlur(radius=30))

    buffer = BytesIO()
    blurred.save(buffer, format="JPEG", quality=85)
    buffer.seek(0)

    input_file = BufferedInputFile(buffer.read(), filename="blurred.jpg")

    # Upload it by sending to this viewer (first time only) - capture the new file_id
    sent = await bot.send_photo(chat_id=viewer_chat_id, photo=input_file)
    new_file_id = sent.photo[-1].file_id

    media_obj.blurred_file_id = new_file_id
    await session.commit()

    # Delete that upload message - it was only sent to mint a file_id, not for the viewer to see yet.
    # The caller will send the "real" blurred message (with the reveal button) separately.
    try:
        await bot.delete_message(chat_id=viewer_chat_id, message_id=sent.message_id)
    except Exception:
        pass

    return new_file_id


async def _schedule_reblur(chat_id: int, message_id: int, blurred_file_id: str, delay_seconds: int):
    """After `delay_seconds`, swap the revealed photo back to blurred. One-time only - no further reveals."""
    import asyncio

    async def _reblur():
        await asyncio.sleep(max(delay_seconds, 2))  # minimum 2s so "instant" is still visible at all
        try:
            await bot.edit_message_media(
                chat_id=chat_id,
                message_id=message_id,
                media=InputMediaPhoto(media=blurred_file_id, caption="🔒 Already revealed"),
            )
        except Exception as e:
            logger.log("PHOTO_REVEAL", f"Re-blur failed (message likely deleted/changed): {e}")

    task = asyncio.create_task(_reblur())
    _pending_reblur_tasks.add(task)
    task.add_done_callback(_pending_reblur_tasks.discard)


async def _send_profile_photos(
    chat_id: int,
    viewer_id: int,
    profile: ProfileModel,
    media_items: list[ProfileMediaModel],
    caption_text: str,
    session: AsyncSession,
) -> None:
    """
    Sends a profile's photos to a viewer, handling per-photo blur/reveal independently.
    Falls back to a fast single media-group album when NO photos have blur enabled
    (preserves the original snappy UX for users who opt out of blur entirely).
    """
    any_blur_enabled = any(m.reveal_duration is not None for m in media_items)

    if not media_items:
        await bot.send_message(chat_id=chat_id, text=caption_text)
        return

    if not any_blur_enabled:
        # Fast path: original album behavior, unchanged
        media_list = []
        for i, media_obj in enumerate(media_items):
            if i == 0:
                media_list.append(
                    InputMediaPhoto(media=media_obj.media, caption=caption_text, parse_mode=None)
                )
            else:
                media_list.append(InputMediaPhoto(media=media_obj.media))
        await bot.send_media_group(chat_id=chat_id, media=media_list)
        return

    # Slow path: at least one photo needs individual handling for its reveal button
    for i, media_obj in enumerate(media_items):
        caption = caption_text if i == 0 else None

        if media_obj.reveal_duration is None:
            # This specific photo has blur disabled - show normally
            await bot.send_photo(chat_id=chat_id, photo=media_obj.media, caption=caption)
            continue

        already_revealed = await PhotoReveal.has_revealed(session, media_obj.id, viewer_id)

        if already_revealed:
            # No second chances - always blurred, no button, from here on forever
            blurred_id = await _get_or_create_blurred_file_id(session, media_obj, chat_id)
            await bot.send_photo(
                chat_id=chat_id,
                photo=blurred_id,
                caption=(caption + "\n🔒 Already revealed") if caption else "🔒 Already revealed",
            )
        else:
            blurred_id = await _get_or_create_blurred_file_id(session, media_obj, chat_id)
            builder = InlineKeyboardBuilder()
            builder.button(
                text="👁 Tap to reveal",
                callback_data=PhotoRevealCallback(media_id=media_obj.id),
            )
            await bot.send_photo(
                chat_id=chat_id,
                photo=blurred_id,
                caption=caption,
                reply_markup=builder.as_markup(),
            )


async def send_profile_with_dist(
    user: UserModel, profile: ProfileModel, session: AsyncSession
) -> None:
    """Отправляет профиль пользователя с расстоянием до него в киломтерах, с учётом blur/reveal"""
    media_items = await ProfileMedia.get_profile_photos(session=session, profile_id=profile.id)

    if user.profile.is_shared_location and profile.is_shared_location:
        distance = haversine_distance(
            user.profile.latitude, user.profile.longitude, profile.latitude, profile.longitude
        )
        city = f"📍 {round(distance, 2)} km"
    else:
        city = profile.city
    text = f"{profile.name}, {profile.age}, {city}\n{profile.description}"

    await _send_profile_photos(
        chat_id=user.id,
        viewer_id=user.id,
        profile=profile,
        media_items=media_items,
        caption_text=text,
        session=session,
    )


async def complaint_to_profile(
    session: AsyncSession, sender: UserModel, receiver: UserModel, reason: str
) -> None:
    """Отправляет в группу модераторов анкету пользователя
    на которого пришла жалоба"""
    if MODERATOR_GROUP_ID:
        try:
            complaint = await Compleint.create(
                session=session,
                sender_id=sender.id,
                receiver_id=receiver.id,
                reason=reason,
            )

            await send_profile(MODERATOR_GROUP_ID, receiver.profile, session)

            text = mt.REPORT_TO_USER.format(
                sender.id,
                sender.username,
                receiver.id,
                receiver.username,
                reason,
            )

            await bot.send_message(
                chat_id=MODERATOR_GROUP_ID,
                text=text,
                reply_markup=block_user_ikb(
                    complaint_id=complaint.id,
                    user_id=receiver.id,
                    username=receiver.username,
                ),
            )
        except:
            logger.error("Сообщение в модераторскую группу не отправленно")