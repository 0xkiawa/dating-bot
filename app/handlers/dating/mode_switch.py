from aiogram import F, types
from aiogram.filters import Filter
from aiogram.filters import Command
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.default.base import mode_confirm_kb, mode_menu_kb, age_range_search_kb
from app.routers import dating_router
from app.states.default import Search
from app.text import message_text as mt
from loader import _
from database.models import UserModel
from database.services import User
from database.services.search import search_profiles
from app.business.profile_service import send_profile_with_dist
from database.services import Profile


class ModeConfirmationFilter(Filter):
    async def __call__(self, message: types.Message) -> dict | bool:
        if message.text == f"✅ {_('Yes, Switch')}":
            return {"switch": True}
        if message.text == f"❌ {_('No, Stay')}":
            return {"switch": False}
        return False


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
    
    if not current_mode:
        await activate_mode(message, state, user, session, new_mode)
        return
    
    if current_mode == new_mode:
        await show_mode_menu(message, new_mode)
        return
    
    await state.update_data(pending_mode=new_mode)
    confirm_text = mt.MODE_SWITCH_CONFIRM(current_mode, new_mode)
    await message.answer(confirm_text, reply_markup=mode_confirm_kb())


@dating_router.message(ModeConfirmationFilter())
async def mode_switch_confirmation(
    message: types.Message,
    state: FSMContext,
    user: UserModel,
    session: AsyncSession,
    switch: bool,
) -> None:
    """Handle mode switch confirmation"""
    data = await state.get_data()
    pending_mode = data.get("pending_mode")
    
    if not pending_mode:
        return
    
    if switch:
        await activate_mode(message, state, user, session, pending_mode)
    else:
        await message.answer(mt.MODE_SWITCH_CANCELLED, reply_markup=mode_menu_kb())
    
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
        await message.answer(mt.MODE_ACTIVATION_ERROR)
        return
    
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
    await message.answer(menu_text, reply_markup=mode_menu_kb())


# Handle Browse Profiles button from mode menu
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
        await message.answer(mt.NO_MODE_SELECTED)
        return
    
    from app.keyboards.default.registration_form import RegistrationFormKb
    await state.set_state(Search.hosting_filter)
    await state.update_data(current_mode=current_mode)
    await message.answer(mt.HOSTING_FILTER, reply_markup=RegistrationFormKb.hosting_filter())


# Handle hosting filter selection
@dating_router.message(StateFilter(Search.hosting_filter), F.text)
async def hosting_filter_handler(
    message: types.Message,
    state: FSMContext,
    user: UserModel,
    session: AsyncSession,
) -> None:
    """Handle hosting filter selection - then ask for role filter"""
    hosting_map = {
        _("🏠 Host"): "yes",
        _("🚫 Can't Host"): "no",
        _("🏨 Airbnb"): "airbnb",
        _("👁️ See All"): "all"
    }
    
    hosting_filter = hosting_map.get(message.text)
    if not hosting_filter:
        await message.answer(mt.INVALID_OPTION)
        return
    
    await state.update_data(hosting_filter=hosting_filter)
    await state.set_state(Search.role_filter)
    
    from app.keyboards.default.registration_form import RegistrationFormKb
    await message.answer(mt.ROLE_FILTER, reply_markup=RegistrationFormKb.role_filter())


# Handle role filter selection - now leads to AGE step instead of searching directly
@dating_router.message(StateFilter(Search.role_filter), F.text)
async def role_filter_handler(
    message: types.Message,
    state: FSMContext,
    user: UserModel,
    session: AsyncSession,
) -> None:
    """Handle role filter selection - then ask for age range"""
    role_map = {
        _("🔝 Tops"): "top",
        _("🔽 Bottoms"): "bottom",
        _("🔄 Verse"): "verse",
        _("👁️ Everyone"): "all"
    }
    
    role_filter = role_map.get(message.text)
    if not role_filter:
        await message.answer(mt.INVALID_OPTION)
        return
    
    # Save role filter, move to age step
    await state.update_data(role_filter=role_filter)
    await state.set_state(Search.age_filter_min)
    
    await message.answer(
        mt.AGE_RANGE_SEARCH_PROMPT,
        reply_markup=age_range_search_kb(),
    )


# NEW: Handle age step - "use default" skips straight to search
@dating_router.message(StateFilter(Search.age_filter_min), F.text == f"✅ {_('Use Default Matching')}")
async def age_filter_use_default(
    message: types.Message,
    state: FSMContext,
    user: UserModel,
    session: AsyncSession,
) -> None:
    """User chose to skip custom age range - search with default (dynamic) age matching"""
    data = await state.get_data()
    current_mode = data.get("current_mode")
    hosting_filter = data.get("hosting_filter", "all")
    role_filter = data.get("role_filter", "all")
    
    await start_mode_search(
        message, state, user, session, current_mode, hosting_filter, role_filter,
        min_age=None, max_age=None,
    )


# NEW: Handle age step - user types a minimum age
@dating_router.message(StateFilter(Search.age_filter_min), F.text.regexp(r"^\d+$"))
async def age_filter_min_input(
    message: types.Message,
    state: FSMContext,
) -> None:
    """User typed a minimum age - ask for maximum next"""
    min_age = int(message.text)
    
    if min_age < 18 or min_age > 99:
        await message.answer(mt.AGE_FILTER_TOO_HIGH if min_age > 99 else mt.AGE_FILTER_TOO_LOW)
        return
    
    await state.update_data(search_min_age=min_age)
    await state.set_state(Search.age_filter_max)
    await message.answer(mt.AGE_RANGE_SEARCH_MAX_PROMPT.format(min_age=min_age))


@dating_router.message(StateFilter(Search.age_filter_min))
async def age_filter_min_invalid(message: types.Message) -> None:
    await message.answer(mt.AGE_FILTER_INVALID_INPUT)


# NEW: Handle age step - user types a maximum age, then search runs
@dating_router.message(StateFilter(Search.age_filter_max), F.text.regexp(r"^\d+$"))
async def age_filter_max_input(
    message: types.Message,
    state: FSMContext,
    user: UserModel,
    session: AsyncSession,
) -> None:
    """User typed a maximum age - run the search with full filters"""
    max_age = int(message.text)
    data = await state.get_data()
    min_age = data.get("search_min_age", 18)
    
    if max_age < min_age:
        await message.answer(mt.AGE_FILTER_INVALID_RANGE.format(min_age=min_age))
        return
    
    if max_age > 99:
        await message.answer(mt.AGE_FILTER_TOO_HIGH)
        return
    
    current_mode = data.get("current_mode")
    hosting_filter = data.get("hosting_filter", "all")
    role_filter = data.get("role_filter", "all")
    
    await start_mode_search(
        message, state, user, session, current_mode, hosting_filter, role_filter,
        min_age=min_age, max_age=max_age,
    )


@dating_router.message(StateFilter(Search.age_filter_max))
async def age_filter_max_invalid(message: types.Message) -> None:
    await message.answer(mt.AGE_FILTER_INVALID_INPUT)


async def start_mode_search(
    message: types.Message,
    state: FSMContext,
    user: UserModel,
    session: AsyncSession,
    mode: str,
    hosting_filter: str = 'all',
    role_filter: str = 'all',
    min_age: int = None,
    max_age: int = None,
) -> None:
    """Start searching in specified mode with hosting, role, and age filters"""
    from app.keyboards.default.base import search_kb
    
    await message.answer(mt.SEARCH, reply_markup=search_kb)
    
    original_find_role = user.profile.find_role
    user.profile.find_role = role_filter
    
    if profile_list := await search_profiles(
        session, 
        user.profile, 
        user_mode=mode, 
        hosting_filter=hosting_filter,
        min_age=min_age,
        max_age=max_age,
    ):
        await state.set_state(Search.search)
        await state.update_data(
            ids=profile_list, 
            current_mode=mode,
            hosting_filter=hosting_filter,
            role_filter=role_filter,
            min_age=min_age,
            max_age=max_age,
        )
        
        first_profile = await Profile.get(session, profile_list[0])
        await send_profile_with_dist(user=user, profile=first_profile, session=session)
    else:
        await message.answer(mt.EMPTY_PROFILE_SEARCH(mode), reply_markup=mode_menu_kb())
    
    user.profile.find_role = original_find_role