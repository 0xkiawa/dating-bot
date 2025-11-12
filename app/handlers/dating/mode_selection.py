from aiogram import F, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.default.base import mode_selection_kb, mode_menu_kb
from app.routers import dating_router
from app.text import message_text as mt
from database.models import UserModel
from database.services import User


@dating_router.message(F.text == "🎭")
async def enter_mode_handler(
    message: types.Message,
    state: FSMContext,
    user: UserModel,
    session: AsyncSession
) -> None:
    """Handle Enter Mode button - show mode selection"""
    await message.answer(mt.SELECT_MODE, reply_markup=mode_selection_kb)


@dating_router.message(F.text.in_(["🍆👅🍑💦 Fun Mode", "❤️🥂 Dating Mode", "🤝 Friends Mode"]))
async def mode_selection_handler(
    message: types.Message,
    state: FSMContext,
    user: UserModel,
    session: AsyncSession
) -> None:
    """Handle mode selection from mode selection menu"""
    # Map button text to mode
    mode_mapping = {
        "🍆👅🍑💦 Fun Mode": "fun",
        "❤️🥂 Dating Mode": "dates",
        "🤝 Friends Mode": "friends"
    }
    
    selected_mode = mode_mapping.get(message.text)
    if not selected_mode:
        return
    
    # Get current mode
    current_mode = await User.get_mode(session, user.id)
    
    # If no current mode, activate new mode
    if not current_mode:
        await activate_mode(message, state, user, session, selected_mode)
        return
    
    # If same mode, show mode menu
    if current_mode == selected_mode:
        await show_mode_menu(message, selected_mode)
        return
    
    # Different mode - ask confirmation
    await state.update_data(pending_mode=selected_mode)
    confirm_text = mt.MODE_SWITCH_CONFIRM(current_mode, selected_mode)
    
    from app.keyboards.default.base import mode_confirm_kb
    await message.answer(confirm_text, reply_markup=mode_confirm_kb())


async def activate_mode(
    message: types.Message,
    state: FSMContext,
    user: UserModel,
    session: AsyncSession,
    mode: str,
) -> None:
    """Activate mode and show mode menu"""
    success = await User.set_mode(session, user.id, mode)
    
    if not success:
        await message.answer("Error activating mode. Please try again.")
        return
    
    # Send mode activation message with mode menu
    mode_messages = {
        "fun": mt.MODE_FUN_ACTIVATED,
        "dates": mt.MODE_DATES_ACTIVATED,
        "friends": mt.MODE_FRIENDS_ACTIVATED,
    }
    
    await message.answer(mode_messages[mode])
    await show_mode_menu(message, mode)


async def show_mode_menu(message: types.Message, mode: str) -> None:
    """Show mode-specific menu"""
    mode_menus = {
        "fun": mt.MODE_FUN_MENU,
        "dates": mt.MODE_DATES_MENU,
        "friends": mt.MODE_FRIENDS_MENU,
    }
    
    menu_text = mode_menus.get(mode, "Select an option:")
    await message.answer(menu_text, reply_markup=mode_menu_kb)