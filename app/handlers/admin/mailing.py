import asyncio

from aiogram import F, types
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.routers import admin_router
from app.states.admin import Mailing
from database.services.profile import Profile
from database.services.user import User
from utils.logging import logger


@admin_router.message(StateFilter(None), Command("mailing"))
@admin_router.message(StateFilter(None), F.text == "📨 Mailing")
async def users_mailing_panel(message: types.Message, state: FSMContext) -> None:
    """Admin panel for user mailing."""
    await message.answer(
        "📢 Send your message for mailing.\n"
        "You can send text, photo, video, or document. It will be forwarded to all users.\n\n"
        "💡 Tip: include <code>{name}</code> anywhere in your text and it'll be replaced "
        "with each user's first name — e.g. 'Hey {name}, ...'\n\n"
        "Send /cancel to abort."
    )
    await state.set_state(Mailing.message)


@admin_router.message(StateFilter(Mailing.message), Command("cancel"))
async def cancel_mailing(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("❌ Mailing cancelled.")


@admin_router.message(StateFilter(Mailing.message))
async def preview_mailing(message: types.Message, state: FSMContext) -> None:
    """Capture the message content (text/media + caption), store it for personalized sending."""
    message_type = "text"
    file_id = None
    text = message.text or message.caption or ""

    if message.photo:
        message_type = "photo"
        file_id = message.photo[-1].file_id
    elif message.video:
        message_type = "video"
        file_id = message.video.file_id
    elif message.document:
        message_type = "document"
        file_id = message.document.file_id

    await state.update_data(
        message_type=message_type,
        file_id=file_id,
        text=text,
    )
    await state.set_state(Mailing.confirm)

    # Preview exactly as admin sent it (NOT personalized - this is just a content check)
    await message.copy_to(chat_id=message.chat.id, reply_markup=None)

    has_placeholder = "{name}" in text
    note = "\n\n👁 This will be personalized with each user's name." if has_placeholder else ""

    await message.answer(
        "⬆️ <b>This is exactly what will be sent to ALL users</b> "
        f"(placeholders filled in per-person).{note}\n\n"
        "Type <b>YES</b> to confirm and send now, or /cancel to abort."
    )


@admin_router.message(StateFilter(Mailing.confirm), Command("cancel"))
async def cancel_mailing_confirm(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("❌ Mailing cancelled.")


@admin_router.message(StateFilter(Mailing.confirm), F.text.upper() == "YES")
async def start_mailing(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    message_type = data["message_type"]
    file_id = data.get("file_id")
    text_template = data.get("text", "")
    await state.clear()

    users = await User.get_all(session)
    sent_count, failed_count, blocked_count = 0, 0, 0
    batch_size = 25
    delay = 1

    for i, user in enumerate(users, 1):
        try:
            # Fetch the user's current first name live from Telegram - no DB storage needed
            name = "there"
            if "{name}" in text_template:
                try:
                    chat = await message.bot.get_chat(user.id)
                    name = chat.first_name or chat.username or "there"
                except Exception:
                    pass  # keep fallback "there"

            personalized_text = text_template.replace("{name}", name) if text_template else None

            if message_type == "text":
                await message.bot.send_message(chat_id=user.id, text=personalized_text)
            elif message_type == "photo":
                await message.bot.send_photo(chat_id=user.id, photo=file_id, caption=personalized_text)
            elif message_type == "video":
                await message.bot.send_video(chat_id=user.id, video=file_id, caption=personalized_text)
            elif message_type == "document":
                await message.bot.send_document(chat_id=user.id, document=file_id, caption=personalized_text)

            sent_count += 1
        except TelegramForbiddenError:
            blocked_count += 1
            await Profile.update(session=session, id=user.id, is_active=False)
            logger.log("MAILING", f"User {user.id} blocked bot - profile deactivated")
        except (TelegramBadRequest, TelegramAPIError) as e:
            failed_count += 1
            logger.log("MAILING", f"Failed to send to user {user.id}: {e}")

        if i % batch_size == 0:
            await asyncio.sleep(delay)

    await message.answer(
        f"✅ Mailing completed!\n"
        f"📬 Sent: {sent_count}\n"
        f"🚫 Blocked (deactivated): {blocked_count}\n"
        f"⚠️ Other failures: {failed_count}"
    )


@admin_router.message(StateFilter(Mailing.confirm))
async def invalid_confirm(message: types.Message) -> None:
    await message.answer("Type <b>YES</b> to confirm and send, or /cancel to abort.")