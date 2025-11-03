from aiogram import F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.default.base import mode_confirm_kb, search_kb
from app.routers import dating_router
from app.states.default import Search
from app.text import message_text as mt
from database.models import UserModel
from database.services import User
from database.services.search import search_profiles
from app.business.profile_service import send_profile_with_dist
from database.services import Profile


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
    - If same mode, start searching
    """
    current_mode = await User.get_mode(session, user.id)
    
    # No active mode - activate new mode
    if not current_mode:
        await activate_mode(message, state, user, session, new_mode)
        return
    
    # Same mode - continue searching
    if current_mode == new_mode:
        await start_mode_search(message, state, user, session, new_mode)
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
        await message.answer(mt.MODE_SWITCH_CANCELLED, reply_markup=search_kb)
    
    await state.update_data(pending_mode=None)


async def activate_mode(
    message: types.Message,
    state: FSMContext,
    user: UserModel,
    session: AsyncSession,
    mode: str,
) -> None:
    """Activate mode and start searching"""
    success = await User.set_mode(session, user.id, mode)
    
    if not success:
        await message.answer("Error activating mode. Please try again.")
        return
    
    # Send mode activation message
    mode_messages = {
        "fun": mt.MODE_FUN_ACTIVATED,
        "dates": mt.MODE_DATES_ACTIVATED,
        "friends": mt.MODE_FRIENDS_ACTIVATED,
    }
    
    await message.answer(mode_messages[mode], reply_markup=search_kb)
    await start_mode_search(message, state, user, session, mode)


async def start_mode_search(
    message: types.Message,
    state: FSMContext,
    user: UserModel,
    session: AsyncSession,
    mode: str,
) -> None:
    """Start searching in specified mode"""
    await message.answer(mt.SEARCH, reply_markup=search_kb)
    
    # Search profiles with mode filter
    if profile_list := await search_profiles(session, user.profile, user_mode=mode):
        await state.set_state(Search.search)
        await state.update_data(ids=profile_list, current_mode=mode)
        
        first_profile = await Profile.get(session, profile_list[0])
        await send_profile_with_dist(user=user, profile=first_profile, session=session)
    else:
        await message.answer(mt.INVALID_PROFILE_SEARCH)