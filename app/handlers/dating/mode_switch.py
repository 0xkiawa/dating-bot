from aiogram import F, types
from aiogram.filters import Command
from aiogram.filters.state import StateFilter  # ADD StateFilter import
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.default.base import mode_confirm_kb, mode_menu_kb
from app.routers import dating_router
from app.states.default import Search
from app.text import message_text as mt
from database.models import UserModel
from database.services import User
from database.services.search import search_profiles
from app.business.profile_service import send_profile_with_dist
from database.services import Profile


# Command handlers for direct mode access
@dating_router.message(Command("fun"))
async def fun_mode_command(
    message: types.Message, 
    state: FSMContext, 
    user: UserModel, 
    session: AsyncSession
) -> None:
    """Handle /fun command - Switch to fun mode"""
    await handle_mode_switch(message, state, user, session, "fun")


@dating_router.message(Command("dates"))
async def dates_mode_command(
    message: types.Message, 
    state: FSMContext, 
    user: UserModel, 
    session: AsyncSession
) -> None:
    """Handle /dates command - Switch to dates mode"""
    await handle_mode_switch(message, state, user, session, "dates")


@dating_router.message(Command("friends"))
async def friends_mode_command(
    message: types.Message, 
    state: FSMContext, 
    user: UserModel, 
    session: AsyncSession
) -> None:
    """Handle /friends command - Switch to friends mode"""
    await handle_mode_switch(message, state, user, session, "friends")


async def handle_mode_switch(
    message: types.Message,
    state: FSMContext,
    user: UserModel,
    session: AsyncSession,
    new_mode: str,
) -> None:
    """
    Handle mode switching logic:
    - If no current mode, activate new mode
    - If different mode, ask for confirmation
    - If same mode, show mode menu
    """
    current_mode = await User.get_mode(session, user.id)
    
    # No active mode - activate new mode
    if not current_mode:
        await activate_mode(message, state, user, session, new_mode)
        return
    
    # Same mode - show mode menu
    if current_mode == new_mode:
        await show_mode_menu(message, new_mode)
        return
    
    # Different mode - ask confirmation
    await state.update_data(pending_mode=new_mode)
    confirm_text = mt.MODE_SWITCH_CONFIRM(current_mode, new_mode)
    await message.answer(confirm_text, reply_markup=mode_confirm_kb())


@dating_router.message(F.text.in_(["✅ Yes, Switch", "❌ No, Stay"]))
async def mode_switch_confirmation(
    message: types.Message,
    state: FSMContext,
    user: UserModel,
    session: AsyncSession,
) -> None:
    """Handle mode switch confirmation"""
    data = await state.get_data()
    pending_mode = data.get("pending_mode")
    
    if not pending_mode:
        return
    
    if message.text == "✅ Yes, Switch":
        await activate_mode(message, state, user, session, pending_mode)
    else:
        await message.answer(mt.MODE_SWITCH_CANCELLED, reply_markup=mode_menu_kb)
    
    await state.update_data(pending_mode=None)


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


# NEW: Handle Browse Profiles button from mode menu
@dating_router.message(F.text == "🔍")
async def browse_profiles_handler(
    message: types.Message,
    state: FSMContext,
    user: UserModel,
    session: AsyncSession,
) -> None:
    """Handle Browse Profiles button - show hosting filter first"""
    current_mode = await User.get_mode(session, user.id)
    
    if not current_mode:
        await message.answer("Please select a mode first: /fun, /dates, or /friends")
        return
    
    # Show hosting filter prompt
    from app.keyboards.default.registration_form import RegistrationFormKb
    await state.set_state(Search.hosting_filter)
    await state.update_data(current_mode=current_mode)
    await message.answer(mt.HOSTING_FILTER, reply_markup=RegistrationFormKb.hosting_filter())


# NEW: Handle hosting filter selection
@dating_router.message(StateFilter(Search.hosting_filter), F.text)
async def hosting_filter_handler(
    message: types.Message,
    state: FSMContext,
    user: UserModel,
    session: AsyncSession,
) -> None:
    """Handle hosting filter selection"""
    # Map button text to filter values
    hosting_map = {
        "🏠 Host": "yes",
        "🚫 Can't Host": "no",
        "🏨 Airbnb": "airbnb",
        "👁️ See All": "all"
    }
    
    hosting_filter = hosting_map.get(message.text)
    if not hosting_filter:
        await message.answer("Please select a valid option.")
        return
    
    data = await state.get_data()
    current_mode = data.get("current_mode")
    
    # Start search with hosting filter
    await start_mode_search(message, state, user, session, current_mode, hosting_filter)


async def start_mode_search(
    message: types.Message,
    state: FSMContext,
    user: UserModel,
    session: AsyncSession,
    mode: str,
    hosting_filter: str = 'all',  # NEW: default to 'all'
) -> None:
    """Start searching in specified mode with hosting filter"""
    from app.keyboards.default.base import search_kb
    
    await message.answer(mt.SEARCH, reply_markup=search_kb)
    
    # Search profiles with mode and hosting filter
    if profile_list := await search_profiles(session, user.profile, user_mode=mode, hosting_filter=hosting_filter):
        await state.set_state(Search.search)
        await state.update_data(ids=profile_list, current_mode=mode)
        
        first_profile = await Profile.get(session, profile_list[0])
        await send_profile_with_dist(user=user, profile=first_profile, session=session)
    else:
        await message.answer(mt.EMPTY_PROFILE_SEARCH(mode), reply_markup=mode_menu_kb)