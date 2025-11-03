from aiogram import F, types
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

import app.filters.create_profile_filtres as filters
from app.business.dating_service import send_user_like_alert
from app.business.menu_service import menu
from app.business.profile_service import complaint_to_profile, send_profile_with_dist
from app.handlers.common.start import start_command
from app.keyboards.default.base import return_to_menu_kb, search_kb
from app.keyboards.default.compleint import compleint_kb
from app.routers import dating_router
from app.states.default import Search
from app.text import message_text as mt
from database.models import UserModel
from database.services import Match, Profile, User
from database.services.search import search_profiles


@dating_router.message(StateFilter(None), F.text == "🔍")
async def _search_command(
    message: types.Message, state: FSMContext, user: UserModel, session: AsyncSession
) -> None:
    """Bot finds profiles matching user preferences and suggests them"""

    await message.answer(mt.SEARCH, reply_markup=search_kb)

    # Get user's current mode for filtering
    user_mode = await User.get_mode(session, user.id)
    
    if profile_list := await search_profiles(session, user.profile, user_mode=user_mode):
        await state.set_state(Search.search)
        await state.update_data(ids=profile_list, current_mode=user_mode)

        another_profile = await Profile.get(session, profile_list[0])
        await send_profile_with_dist(user=user, profile=another_profile, session=session)

    else:
        await message.answer(mt.INVALID_PROFILE_SEARCH)
        await menu(message.from_user.id)


@dating_router.message(
    StateFilter(Search.search),
    F.text.in_(("❤️", "👎", "💢", "📩")),
)
async def _search_profile(
    message: types.Message, state: FSMContext, user: UserModel, session: AsyncSession
) -> None:
    """
    User can interact with profiles suggested by bot,
    by liking or disliking.
    Complaint feature available for profiles with unwanted content.
    All complaints sent to moderator group if specified in settings.
    """
    data = await state.get_data()
    profile_list = data.get("ids", [])
    another_user = await User.get_with_profile(session, profile_list[0])

    if message.text == "❤️":
        await like_profile(
            session=session,
            message=message,
            another_user=another_user,
        )
    elif message.text == "👎":
        pass
    elif message.text == "📩":
        await state.set_state(Search.message)
        await message.answer(mt.MAILING_TO_USER, reply_markup=return_to_menu_kb)
        return

    if message.text == "💢":
        await message.answer(mt.COMPLAINT, reply_markup=compleint_kb())
        return
    await next_profile(session, message, profile_list, user, state)


@dating_router.message(StateFilter(Search.search), F.text.in_(("🔞", "💰", "🔫", "↩️")))
async def _search_profile_compleint(
    message: types.Message, state: FSMContext, user: UserModel, session: AsyncSession
) -> None:
    """User can send complaint about profile if it contains unwanted content."""
    data = await state.get_data()
    profile_list = data.get("ids", [])
    another_user = await User.get_with_profile(session, profile_list[0])

    if message.text in ("🔞", "💰", "🔫"):
        await message.answer(mt.REPORT_TO_PROFILE, reply_markup=search_kb)

        await complaint_to_profile(
            session=session,
            sender=user,
            receiver=another_user,
            reason=message.text,
        )
    elif message.text == "↩️":
        await message.answer(mt.SEARCH, reply_markup=search_kb)
    await next_profile(session, message, profile_list, user, state)


@dating_router.message(StateFilter(Search.message), F.text, filters.IsMessageToUser())
async def _search_profile_mailing_(
    message: types.Message, state: FSMContext, user: UserModel, session: AsyncSession
) -> None:
    """Catches messages that user sends in response to profile"""
    data = await state.get_data()
    profile_list = data.get("ids", [])
    another_user = await User.get_with_profile(session, profile_list[0])
    await state.set_state(Search.search)

    if message.text == "↩️":
        await message.answer(mt.CANNCELED_LETTER, reply_markup=search_kb)
        await send_profile_with_dist(user=user, profile=another_user.profile, session=session)

        return
    await like_profile(
        session=session,
        message=message,
        another_user=another_user,
        mail_text=message.text,
    )
    await message.answer(mt.MAILING_LIKE, reply_markup=search_kb)
    await next_profile(session, message, profile_list, user, state)


@dating_router.message(StateFilter(Search.message))
async def _search_profile_mailing_error(message: types.Message) -> None:
    """Catches error if user sends message not matching template"""
    await message.answer(mt.INVALID_MAILING_TO_USER)


async def next_profile(
    session: AsyncSession,
    message: types.Message,
    profile_list: UserModel,
    user: UserModel,
    state: FSMContext,
):
    profile_list.pop(0)
    if profile_list:
        profile = await Profile.get(session, profile_list[0])
        await state.update_data(ids=profile_list)
        await send_profile_with_dist(user=user, profile=profile, session=session)
    else:
        await message.answer(mt.EMPTY_PROFILE_SEARCH)
        await start_command(message=message, user=user, state=state)


async def like_profile(
    session: AsyncSession,
    message: types.Message,
    another_user: UserModel,
    mail_text: str | None = None,
):
    is_create = await Match.create(session, message.from_user.id, another_user.id, mail_text)

    if is_create:
        matchs_count = len(await Match.get_user_matchs(session, another_user.id))
        if matchs_count == 1 or matchs_count == 2 or matchs_count % 3 == 0:
            await send_user_like_alert(session, another_user)