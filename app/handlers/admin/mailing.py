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
        "Send /cancel to abort."
    )
    await state.set_state(Mailing.message)


@admin_router.message(StateFilter(Mailing.message), Command("cancel"))
async def cancel_mailing(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("❌ Mailing cancelled.")


@admin_router.message(StateFilter(Mailing.message))
async def preview_mailing(message: types.Message, state: FSMContext) -> None:
    """Store the message and show admin exactly what will be sent, before sending it."""
    await state.update_data(
        chat_id=message.chat.id,
        message_id=message.message_id,
    )
    await state.set_state(Mailing.confirm)

    # Show it back exactly as users will receive it
    await message.copy_to(chat_id=message.chat.id, reply_markup=None)

    await message.answer(
        "⬆️ <b>This is exactly what will be sent to ALL users.</b>\n\n"
        "Type <b>YES</b> to confirm and send now, or /cancel to abort."
    )


@admin_router.message(StateFilter(Mailing.confirm), Command("cancel"))
async def cancel_mailing_confirm(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("❌ Mailing cancelled.")


@admin_router.message(StateFilter(Mailing.confirm), F.text.upper() == "YES")
async def start_mailing(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    source_chat_id = data["chat_id"]
    source_message_id = data["message_id"]
    await state.clear()

    users = await User.get_all(session)
    sent_count, failed_count, blocked_count = 0, 0, 0
    batch_size = 25  # чуть меньше лимита
    delay = 1  # секунда

    for i, user in enumerate(users, 1):
        try:
            await message.bot.copy_message(
                chat_id=user.id,
                from_chat_id=source_chat_id,
                message_id=source_message_id,
                reply_markup=None,
            )
            sent_count += 1
        except TelegramForbiddenError:
            # Бот заблокирован пользователем
            blocked_count += 1
            await Profile.update(session=session, id=user.id, is_active=False)
            logger.log("MAILING", f"User {user.id} blocked bot - profile deactivated")
        except (TelegramBadRequest, TelegramAPIError) as e:
            # Другие ошибки (пользователь удален, чат не найден и т.д.)
            failed_count += 1
            logger.log("MAILING", f"Failed to send to user {user.id}: {e}")

        if i % batch_size == 0:
            await asyncio.sleep(delay)  # пауза после каждой пачки

    await message.answer(
        f"✅ Mailing completed!\n"
        f"📬 Sent: {sent_count}\n"
        f"🚫 Blocked (deactivated): {blocked_count}\n"
        f"⚠️ Other failures: {failed_count}"
    )


@admin_router.message(StateFilter(Mailing.confirm))
async def invalid_confirm(message: types.Message) -> None:
    await message.answer("Type <b>YES</b> to confirm and send, or /cancel to abort.")  