from io import BytesIO

from aiogram.types import BufferedInputFile, InlineKeyboardButton, InputMediaPhoto
from aiogram.utils.keyboard import InlineKeyboardBuilder
from PIL import Image, ImageFilter
from sqlalchemy.ext.asyncio import AsyncSession

from app.filters.kb_filter import CarouselNavCallback, PhotoRevealCallback
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

    file = await bot.get_file(media_obj.media)
    file_bytes_io = BytesIO()
    await bot.download_file(file.file_path, destination=file_bytes_io)
    file_bytes_io.seek(0)

    img = Image.open(file_bytes_io).convert("RGB")
    blurred = img.filter(ImageFilter.GaussianBlur(radius=30))

    buffer = BytesIO()
    blurred.save(buffer, format="JPEG", quality=85)
    buffer.seek(0)

    input_file = BufferedInputFile(buffer.read(), filename="blurred.jpg")

    sent = await bot.send_photo(chat_id=viewer_chat_id, photo=input_file)
    new_file_id = sent.photo[-1].file_id

    media_obj.blurred_file_id = new_file_id
    await session.commit()

    try:
        await bot.delete_message(chat_id=viewer_chat_id, message_id=sent.message_id)
    except Exception:
        pass

    return new_file_id


def _build_dots(total: int, index: int) -> str:
    if total <= 1:
        return ""
    # Bigger circle glyphs for a more prominent indicator
    return "\n" + "   ".join("⬤" if i == index else "◯" for i in range(total))


async def build_carousel_page(
    session: AsyncSession,
    profile_id: int,
    media_items: list[ProfileMediaModel],
    index: int,
    viewer_id: int,
    caption_text: str,
):
    """
    Builds everything needed to show ONE page of a profile's photo carousel:
    the photo to send, the full caption (with dots), and the nav/reveal keyboard.
    Used both for the initial send and for every ◀️▶️ navigation tap.
    """
    total = len(media_items)
    media_obj = media_items[index]
    dots = _build_dots(total, index)

    photo_id = media_obj.media
    extra_caption = ""
    show_reveal_button = False

    if media_obj.reveal_duration is not None:
        revealed = await PhotoReveal.has_revealed(session, media_obj.id, viewer_id)
        photo_id = await _get_or_create_blurred_file_id(session, media_obj, viewer_id)
        if revealed:
            extra_caption = "\n🔒 Already revealed"
        else:
            show_reveal_button = True

    buttons = []
    if index > 0:
        buttons.append(
            InlineKeyboardButton(
                text="←",
                callback_data=CarouselNavCallback(profile_id=profile_id, index=index - 1).pack(),
            )
        )

    # Always-visible counter, centered between the arrows (even on the last page)
    if total > 1:
        buttons.append(
            InlineKeyboardButton(
                text=f"{index + 1}/{total}",
                callback_data=CarouselNavCallback(profile_id=profile_id, index=index).pack(),
            )
        )

    if show_reveal_button:
        buttons.append(
            InlineKeyboardButton(
                text="👁 REVEAL",
                callback_data=PhotoRevealCallback(media_id=media_obj.id).pack(),
            )
        )
    if index < total - 1:
        buttons.append(
            InlineKeyboardButton(
                text="→",
                callback_data=CarouselNavCallback(profile_id=profile_id, index=index + 1).pack(),
            )
        )

    builder = InlineKeyboardBuilder()
    for btn in buttons:
        builder.add(btn)
    if buttons:
        builder.adjust(len(buttons))

    full_caption = f"{caption_text}{dots}{extra_caption}"
    markup = builder.as_markup() if buttons else None

    return photo_id, full_caption, markup


async def _schedule_reblur_carousel(
    chat_id: int,
    message_id: int,
    blurred_file_id: str,
    caption_with_dots: str,
    nav_markup,
    delay_seconds: int,
):
    """
    After `delay_seconds`, DELETES the revealed message entirely and sends a fresh
    blurred one in its place - rather than just editing it back to blurred.

    Why delete instead of edit: Telegram's "Shared Media" tab for a chat reflects
    the live state of messages. Editing a message back to blurred can still leave
    traces of the clear version cached. Deleting the message is the one behavior
    that reliably scrubs it from Shared Media across Telegram clients - a fresh
    message with the blurred photo is sent immediately after, so the carousel
    still works, it just appears as a new message rather than updating in place.
    """
    import asyncio

    async def _reblur():
        await asyncio.sleep(max(delay_seconds, 2))  # minimum 2s so "instant" is still visible at all
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception as e:
            logger.log("PHOTO_REVEAL", f"Could not delete revealed message: {e}")

        try:
            await bot.send_photo(
                chat_id=chat_id,
                photo=blurred_file_id,
                caption=caption_with_dots + "\n🔒 Already revealed",
                reply_markup=nav_markup,
            )
        except Exception as e:
            logger.log("PHOTO_REVEAL", f"Could not send fresh blurred photo: {e}")

    task = asyncio.create_task(_reblur())
    _pending_reblur_tasks.add(task)
    task.add_done_callback(_pending_reblur_tasks.discard)


async def send_profile_with_dist(
    user: UserModel, profile: ProfileModel, session: AsyncSession
) -> None:
    """Отправляет профиль пользователя с расстоянием, как карусель фото (◀️▶️ + точки + reveal)"""
    media_items = await ProfileMedia.get_profile_photos(session=session, profile_id=profile.id)

    if user.profile.is_shared_location and profile.is_shared_location:
        distance = haversine_distance(
            user.profile.latitude, user.profile.longitude, profile.latitude, profile.longitude
        )
        city = f"📍 {round(distance, 2)} km"
    else:
        city = profile.city
    text = f"{profile.name}, {profile.age}, {city}\n{profile.description}"

    if not media_items:
        await bot.send_message(chat_id=user.id, text=text)
        return

    photo_id, caption, markup = await build_carousel_page(
        session=session,
        profile_id=profile.id,
        media_items=media_items,
        index=0,
        viewer_id=user.id,
        caption_text=text,
    )
    await bot.send_photo(chat_id=user.id, photo=photo_id, caption=caption, reply_markup=markup)


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