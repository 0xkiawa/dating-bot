import asyncio
from functools import wraps

from aiogram import F, types
from aiogram.filters import Command, Filter
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardRemove
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.business.menu_service import answer_inline_message
from database.services.share import (
    get_pending_shared_target,
    insert_shared_profile,
)
from app.filters.kb_filter import BrowseFilterCallback, ModeMenuCallback, UnblockUserCallback
from app.handlers.dating.search import next_profile
from app.keyboards.inline.menus import (
    blocked_users_ikb,
    main_menu_ikb,
    mode_confirm_ikb,
    mode_menu_ikb,
    mode_selection_ikb,
)
from app.keyboards.inline.search_filters import (
    age_range_ikb,
    custom_age_ikb,
    hosting_filter_ikb,
    role_filter_ikb,
)
from app.routers import common_router, dating_router
from app.states.default import Search
from app.text import message_text as mt
from database.models import ProfileModel, UserBlockModel, UserModel
from database.services import User
from database.services.search import search_profiles
from loader import _


_browse_filter_locks: dict[int, asyncio.Lock] = {}


def _serialize_browse_filter_callbacks(handler):
    @wraps(handler)
    async def wrapped(callback: types.CallbackQuery, *args, **kwargs):
        lock = _browse_filter_locks.setdefault(
            callback.from_user.id, asyncio.Lock()
        )
        async with lock:
            return await handler(callback, *args, **kwargs)

    return wrapped


class ModeConfirmationFilter(Filter):
    async def __call__(self, message: types.Message) -> dict | bool:
        if message.text == f"✅ {_('Yes, Switch')}":
            return {"switch": True}
        if message.text == f"❌ {_('No, Stay')}":
            return {"switch": False}
        return False


# Command handlers for direct mode access
@common_router.message(Command("fun"))
async def fun_mode_command(
    message: types.Message, 
    state: FSMContext, 
    user: UserModel, 
    session: AsyncSession
) -> None:
    """Handle /fun command - Switch to fun mode"""
    await handle_mode_switch(message, state, user, session, "fun")


@common_router.message(Command("dates"))
async def dates_mode_command(
    message: types.Message, 
    state: FSMContext, 
    user: UserModel, 
    session: AsyncSession
) -> None:
    """Handle /dates command - Switch to dates mode"""
    await handle_mode_switch(message, state, user, session, "dates")


@common_router.message(Command("friends"))
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
    # Mode commands intentionally interrupt any active flow (for example, a search).
    await state.clear()
    current_mode = await User.get_mode(session, user.id)
    
    if not current_mode:
        await activate_mode(message, state, user, session, new_mode)
        return
    
    if current_mode == new_mode:
        await show_mode_menu(message, new_mode)
        return
    
    await state.update_data(pending_mode=new_mode)
    confirm_text = mt.MODE_SWITCH_CONFIRM(current_mode, new_mode)
    await answer_inline_message(message, confirm_text, mode_confirm_ikb())


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
        await answer_inline_message(message, mt.MODE_SWITCH_CANCELLED, mode_menu_ikb())
    
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
    await answer_inline_message(message, mode_menu_text(mode), mode_menu_ikb())


def mode_menu_text(mode: str | None) -> str:
    mode_menus = {
        "fun": mt.MODE_FUN_MENU,
        "dates": mt.MODE_DATES_MENU,
        "friends": mt.MODE_FRIENDS_MENU,
    }
    return mode_menus.get(mode, mt.NO_MODE_SELECTED)


@dating_router.callback_query(ModeMenuCallback.filter())
async def mode_menu_callback(
    callback: types.CallbackQuery,
    callback_data: ModeMenuCallback,
    state: FSMContext,
    user: UserModel,
    session: AsyncSession,
) -> None:
    await callback.answer()

    if callback_data.action == "menu":
        await state.clear()
        await callback.message.edit_text(mt.MENU, reply_markup=main_menu_ikb())
    elif callback_data.action == "back":
        await state.clear()
        await callback.message.edit_text(mt.SELECT_MODE, reply_markup=mode_selection_ikb())
    elif callback_data.action in {"browse", "hosting", "age"}:
        await _start_browse_filter(
            callback.message, state, user, session, edit_in_place=True
        )
    elif callback_data.action == "likes":
        from app.handlers.dating.inbox import show_match_archive

        await show_match_archive(
            callback.message,
            state,
            user,
            session,
            username=callback.from_user.username,
        )
    elif callback_data.action == "preferences":
        from app.handlers.dating.preferences import show_preferences

        await show_preferences(callback.message, user)
    elif callback_data.action == "blocks":
        await show_blocked_users(callback.message, user, session)
    else:
        await callback.message.edit_text(mt.INVALID_OPTION, reply_markup=mode_menu_ikb())


async def show_blocked_users(message: types.Message, user: UserModel, session: AsyncSession) -> None:
    result = await session.execute(
        select(UserBlockModel.blocked_id, ProfileModel.name)
        .outerjoin(ProfileModel, ProfileModel.id == UserBlockModel.blocked_id)
        .where(UserBlockModel.blocker_id == user.id)
        .order_by(UserBlockModel.id)
    )
    blocked = [
        (blocked_id, (name or f"User {blocked_id}")[:40])
        for blocked_id, name in result.all()
    ]
    if not blocked:
        await message.edit_text(_("You haven't blocked anyone."), reply_markup=mode_menu_ikb())
        return
    await message.edit_text(
        _("Blocked users are hidden in every mode. Choose someone to unblock."),
        reply_markup=blocked_users_ikb(blocked),
    )


@dating_router.callback_query(UnblockUserCallback.filter())
async def unblock_user_callback(
    callback: types.CallbackQuery,
    callback_data: UnblockUserCallback,
    user: UserModel,
    session: AsyncSession,
) -> None:
    await User.unblock(session, user.id, callback_data.user_id)
    await callback.answer(_("Unblocked"))
    await show_blocked_users(callback.message, user, session)


# Handle Browse Profiles button from mode menu
@dating_router.message(F.text == "🔍")
async def browse_profiles_handler(
    message: types.Message,
    state: FSMContext,
    user: UserModel,
    session: AsyncSession,
) -> None:
    """Handle Browse Profiles button - show hosting filter first"""
    await _start_browse_filter(message, state, user, session)


@dating_router.message(F.text == "🏠")
async def hosting_filter_start_legacy(
    message: types.Message,
    state: FSMContext,
    user: UserModel,
    session: AsyncSession,
) -> None:
    """Keep the old hosting button working during the inline menu rollout."""
    await _start_browse_filter(message, state, user, session)


async def _start_browse_filter(
    message: types.Message,
    state: FSMContext,
    user: UserModel,
    session: AsyncSession,
    edit_in_place: bool = False,
) -> None:
    current_mode = await User.get_mode(session, user.id)
    
    if not current_mode:
        if edit_in_place:
            await message.edit_text(mt.NO_MODE_SELECTED, reply_markup=mode_selection_ikb())
        else:
            await message.answer(mt.NO_MODE_SELECTED)
        return
    
    await state.clear()
    await state.set_state(Search.hosting_filter)
    await state.update_data(current_mode=current_mode, filter_screen="hosting")
    if edit_in_place:
        await message.edit_text(mt.HOSTING_FILTER, reply_markup=hosting_filter_ikb())
    else:
        await answer_inline_message(message, mt.HOSTING_FILTER, hosting_filter_ikb())


@dating_router.callback_query(BrowseFilterCallback.filter())
@_serialize_browse_filter_callbacks
async def browse_filter_callback(
    callback: types.CallbackQuery,
    callback_data: BrowseFilterCallback,
    state: FSMContext,
    user: UserModel,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    current_screen = data.get("filter_screen")

    if callback_data.step == "back":
        expected_screens = {
            "mode_menu": {"hosting"},
            "hosting": {"role"},
            "role": {"age"},
            "age": {"custom_min", "custom_max"},
        }
        if current_screen not in expected_screens.get(callback_data.value, set()):
            await callback.answer("This step has expired.")
            return
    elif current_screen != callback_data.step:
        await callback.answer("This step has expired.")
        return

    await callback.answer()

    if callback_data.step == "back":
        if callback_data.value == "mode_menu":
            mode = data.get("current_mode") or await User.get_mode(session, user.id)
            await state.clear()
            await callback.message.edit_text(
                mode_menu_text(mode), reply_markup=mode_menu_ikb()
            )
        elif callback_data.value == "hosting":
            await state.set_state(Search.hosting_filter)
            await state.update_data(filter_screen="hosting")
            await callback.message.edit_text(
                mt.HOSTING_FILTER, reply_markup=hosting_filter_ikb()
            )
        elif callback_data.value == "role":
            await state.set_state(Search.role_filter)
            await state.update_data(filter_screen="role")
            await callback.message.edit_text(mt.ROLE_FILTER, reply_markup=role_filter_ikb())
        elif callback_data.value == "age":
            await state.set_state(Search.age_filter_min)
            await state.update_data(filter_screen="age", search_min_age=None)
            await callback.message.edit_text(
                mt.AGE_RANGE_SEARCH_PROMPT, reply_markup=age_range_ikb()
            )
        return

    if callback_data.step == "hosting":
        if callback_data.value not in {"yes", "no", "airbnb", "all"}:
            await callback.message.edit_text(
                mt.INVALID_OPTION, reply_markup=hosting_filter_ikb()
            )
            return
        await state.set_state(Search.role_filter)
        await state.update_data(
            hosting_filter=callback_data.value,
            role_filter=None,
            search_min_age=None,
            filter_screen="role",
        )
        await callback.message.edit_text(mt.ROLE_FILTER, reply_markup=role_filter_ikb())
        return

    if callback_data.step == "role":
        if callback_data.value not in {"top", "bottom", "verse", "all"}:
            await callback.message.edit_text(mt.INVALID_OPTION, reply_markup=role_filter_ikb())
            return
        await state.set_state(Search.age_filter_min)
        await state.update_data(
            role_filter=callback_data.value,
            search_min_age=None,
            filter_screen="age",
        )
        await callback.message.edit_text(
            mt.AGE_RANGE_SEARCH_PROMPT, reply_markup=age_range_ikb()
        )
        return

    if callback_data.step != "age":
        await callback.message.edit_text(mt.INVALID_OPTION, reply_markup=age_range_ikb())
        return

    if callback_data.value == "custom":
        await state.set_state(Search.age_filter_min)
        await state.update_data(
            filter_screen="custom_min",
            browse_filter_chat_id=callback.message.chat.id,
            browse_filter_message_id=callback.message.message_id,
            search_min_age=None,
        )
        await callback.message.edit_text(
            mt.AGE_RANGE_CUSTOM_MIN_PROMPT, reply_markup=custom_age_ikb()
        )
        return

    age_ranges = {
        "18_25": (18, 25),
        "26_35": (26, 35),
        "36_45": (36, 45),
        "46_plus": (46, 99),
        "default": (None, None),
    }
    if callback_data.value not in age_ranges:
        await callback.message.edit_text(
            mt.INVALID_OPTION, reply_markup=age_range_ikb()
        )
        return

    min_age, max_age = age_ranges[callback_data.value]
    await start_mode_search(
        callback.message,
        state,
        user,
        session,
        data.get("current_mode"),
        hosting_filter=data.get("hosting_filter", "all"),
        role_filter=data.get("role_filter", "all"),
        min_age=min_age,
        max_age=max_age,
        browse_filter_chat_id=callback.message.chat.id,
        browse_filter_message_id=callback.message.message_id,
    )


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
    
    await state.update_data(
        hosting_filter=hosting_filter,
        role_filter=None,
        search_min_age=None,
        filter_screen="role",
    )
    await state.set_state(Search.role_filter)
    await answer_inline_message(message, mt.ROLE_FILTER, role_filter_ikb())


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
        _("🍆 Tops"): "top",
        _("🍑 Bottoms"): "bottom",
        _("🍆🍑💦 Verse"): "verse",
        _("👬 Everyone"): "all"
    }
    
    role_filter = role_map.get(message.text)
    if not role_filter:
        await message.answer(mt.INVALID_OPTION)
        return
    
    # Save role filter, move to age step
    await state.update_data(role_filter=role_filter, search_min_age=None, filter_screen="age")
    await state.set_state(Search.age_filter_min)
    await answer_inline_message(message, mt.AGE_RANGE_SEARCH_PROMPT, age_range_ikb())


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
    data = await state.get_data()
    if data.get("filter_screen") == "custom_min":
        await state.update_data(filter_screen="custom_max")
        await message.bot.edit_message_text(
            chat_id=data["browse_filter_chat_id"],
            message_id=data["browse_filter_message_id"],
            text=mt.AGE_RANGE_SEARCH_MAX_PROMPT(min_age),
            reply_markup=custom_age_ikb(),
        )
    else:
        await message.answer(mt.AGE_RANGE_SEARCH_MAX_PROMPT(min_age))
    


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
        await message.answer(mt.AGE_FILTER_INVALID_RANGE(min_age))
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
        browse_filter_chat_id=data.get("browse_filter_chat_id"),
        browse_filter_message_id=data.get("browse_filter_message_id"),
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
    browse_filter_chat_id: int | None = None,
    browse_filter_message_id: int | None = None,
) -> None:
    """Start searching in specified mode with hosting, role, and age filters"""
    if not mode or not user.profile:
        await state.clear()
        text = mt.NO_MODE_SELECTED if not mode else mt.NO_PROFILE_FOR_SEARCH
        if browse_filter_chat_id and browse_filter_message_id:
            await message.bot.edit_message_text(
                chat_id=browse_filter_chat_id,
                message_id=browse_filter_message_id,
                text=text,
                reply_markup=mode_menu_ikb(),
            )
        else:
            await answer_inline_message(message, text, mode_menu_ikb())
        return

    original_find_role = user.profile.find_role
    user.profile.find_role = role_filter
    await message.answer(mt.SEARCH, reply_markup=ReplyKeyboardRemove())

    try:
        profile_list = await search_profiles(
            session,
            user.profile,
            user_mode=mode,
            hosting_filter=hosting_filter,
            min_age=min_age,
            max_age=max_age,
        )
    finally:
        user.profile.find_role = original_find_role

    shared_card_id = None
    pending_shared = await get_pending_shared_target(session, user.id)
    if pending_shared:
        _pending_view, shared_target = pending_shared
        profile_list = insert_shared_profile(profile_list, shared_target.id)
        shared_card_id = shared_target.id

    if profile_list:
        if browse_filter_chat_id and browse_filter_message_id:
            await message.bot.edit_message_reply_markup(
                chat_id=browse_filter_chat_id,
                message_id=browse_filter_message_id,
                reply_markup=None,
            )
        await state.set_state(Search.search)
        await state.update_data(
            ids=profile_list,
            current_mode=mode,
            hosting_filter=hosting_filter,
            role_filter=role_filter,
            min_age=min_age,
            max_age=max_age,
            filter_screen="search",
            shared_card_id=shared_card_id,
            shared_card_mode=(
                pending_shared[1].current_mode if pending_shared else None
            ),
            shared_pending_id=(pending_shared[0].id if pending_shared else None),
        )

        await next_profile(
            session,
            message,
            profile_list,
            user,
            state,
            advance_current=False,
        )
    else:
        await state.clear()
        if browse_filter_chat_id and browse_filter_message_id:
            await message.bot.edit_message_text(
                chat_id=browse_filter_chat_id,
                message_id=browse_filter_message_id,
                text=mt.EMPTY_PROFILE_SEARCH(mode),
                reply_markup=mode_menu_ikb(),
            )
        else:
            await answer_inline_message(
                message, mt.EMPTY_PROFILE_SEARCH(mode), mode_menu_ikb()
            )
