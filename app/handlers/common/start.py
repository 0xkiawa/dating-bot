from aiogram import F, types
from aiogram.filters import Command, CommandStart
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext

from app.business.menu_service import menu
from app.keyboards.default.registration_form import create_profile_kb
from app.routers import common_router
from app.text import message_text as mt
from data.config import LOGO_DIR
from database.models import UserModel


@common_router.message(StateFilter("*"), F.text == "💤")
@common_router.message(StateFilter("*"), Command("cancel"))
@common_router.message(StateFilter("*"), CommandStart())
async def start_command(message: types.Message, user: UserModel, state: FSMContext) -> None:
    """
    Команда /start запускает бота и возвращает пользователя в начальное меню.
    Сброс состояния помогает, если пользователь запутался — всегда можно начать сначала.
    
    UPDATED: Main menu now only shows "My Profile" and "Invite Friends"
    Browse and Inbox are now only accessible from mode menus (/fun, /dates, /friends)
    """
    await state.clear()

    if user.profile:
        await menu(user.id)
    else:
        photo = types.FSInputFile(LOGO_DIR)
        await message.answer_photo(
            photo=photo,
            caption=mt.WELCOME,
            reply_markup=create_profile_kb(),
        )