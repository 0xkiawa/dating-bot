from aiogram import F, types
from aiogram.filters import Command, CommandStart
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext

from app.business.menu_service import answer_inline_message, menu
from app.filters.kb_filter import MainMenuCallback
from app.keyboards.inline.menus import (
    main_menu_ikb,
    mode_selection_ikb,
    welcome_menu_ikb,
)
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
            reply_markup=welcome_menu_ikb(),
        )


@common_router.callback_query(MainMenuCallback.filter(F.action == "menu"))
async def return_to_main_menu(
    callback: types.CallbackQuery, state: FSMContext
) -> None:
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(mt.MENU, reply_markup=main_menu_ikb())


@common_router.callback_query(MainMenuCallback.filter(F.action == "welcome_modes"))
async def enter_modes_from_welcome(
    callback: types.CallbackQuery, state: FSMContext
) -> None:
    """Open mode selection from the welcome photo without editing its caption."""
    await callback.answer()
    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)
    await answer_inline_message(callback.message, mt.SELECT_MODE, mode_selection_ikb())
