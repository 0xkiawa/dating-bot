import asyncio

from aiogram import F, types
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession

import app.filters.create_profile_filtres as filters
from app.business.dating_service import send_user_like_alert
from app.business.menu_service import answer_inline_message
from app.business.profile_service import complaint_to_profile, send_profile_with_dist
from app.filters.kb_filter import ProfileActionCallback
from app.keyboards.inline.menus import mode_menu_ikb
from app.keyboards.inline.profile_actions import (
    message_cancel_ikb,
    report_confirmation_ikb,
    report_reasons_ikb,
)
from app.routers import dating_router
from app.states.default import Search
from app.text import message_text as mt
from database.models import UserModel
from database.models.match import MatchStatus
from database.services import Match, Profile, User
from loader import _


_profile_action_locks: dict[int, asyncio.Lock] = {}


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
    if not profile_list:
        await state.clear()
        await message.answer(
            mt.EMPTY_PROFILE_SEARCH(data.get("current_mode")),
            reply_markup=mode_menu_ikb(),
        )
        return
    await state.set_state(Search.search)
    await state.update_data(message_prompt_message_id=None)
    another_user = await User.get_with_profile(session, profile_list[0])
    if (
        not another_user
        or not another_user.profile
        or not another_user.profile.is_active
        or another_user.profile.age < 18
    ):
        await next_profile(session, message, profile_list, user, state)
        return

    if message.text == "❤️":
        await like_profile(
            session=session,
            message=message,
            another_user=another_user,
        )
    elif message.text == "👎":
        await dislike_profile(
            session=session,
            message=message,
            another_user=another_user,
        )
    elif message.text == "📩":
        await state.set_state(Search.message)
        await message.answer(mt.MAILING_TO_USER, reply_markup=ReplyKeyboardRemove())
        return

    if message.text == "💢":
        await state.update_data(report_pending_id=profile_list[0], report_reason=None)
        await message.answer(
            mt.COMPLAINT, reply_markup=report_reasons_ikb(profile_list[0])
        )
        return
    await next_profile(session, message, profile_list, user, state)


@dating_router.message(StateFilter(Search.search), F.text.in_(("🔞", "💰", "🔫", "↩️")))
async def _search_profile_compleint(
    message: types.Message, state: FSMContext, user: UserModel, session: AsyncSession
) -> None:
    """User can send complaint about profile if it contains unwanted content."""
    data = await state.get_data()
    profile_list = data.get("ids", [])
    if not profile_list:
        await state.clear()
        await message.answer(
            mt.EMPTY_PROFILE_SEARCH(data.get("current_mode")),
            reply_markup=mode_menu_ikb(),
        )
        return
    another_user = await User.get_with_profile(session, profile_list[0])
    if (
        not another_user
        or not another_user.profile
        or not another_user.profile.is_active
        or another_user.profile.age < 18
    ):
        await next_profile(session, message, profile_list, user, state)
        return

    if message.text in ("🔞", "💰", "🔫"):
        await message.answer(mt.REPORT_TO_PROFILE, reply_markup=ReplyKeyboardRemove())

        await complaint_to_profile(
            session=session,
            sender=user,
            receiver=another_user,
            reason=message.text,
        )
    elif message.text == "↩️":
        await message.answer(mt.SEARCH, reply_markup=ReplyKeyboardRemove())
    await next_profile(session, message, profile_list, user, state)


@dating_router.message(StateFilter(Search.message), F.text, filters.IsMessageToUser())
async def _search_profile_mailing_(
    message: types.Message, state: FSMContext, user: UserModel, session: AsyncSession
) -> None:
    """Catches messages that user sends in response to profile"""
    data = await state.get_data()
    profile_list = data.get("ids", [])
    if not profile_list:
        await state.clear()
        await message.answer(
            mt.EMPTY_PROFILE_SEARCH(data.get("current_mode")),
            reply_markup=mode_menu_ikb(),
        )
        return
    await state.set_state(Search.search)
    await state.update_data(message_prompt_message_id=None)
    another_user = await User.get_with_profile(session, profile_list[0])
    if (
        not another_user
        or not another_user.profile
        or not another_user.profile.is_active
        or another_user.profile.age < 18
    ):
        await next_profile(session, message, profile_list, user, state)
        return
    if message.text == "↩️":
        await message.answer(mt.CANNCELED_LETTER, reply_markup=ReplyKeyboardRemove())
        return
    await like_profile(
        session=session,
        message=message,
        another_user=another_user,
        mail_text=message.text,
    )
    await message.answer(mt.MAILING_LIKE, reply_markup=ReplyKeyboardRemove())
    await next_profile(session, message, profile_list, user, state)


@dating_router.message(StateFilter(Search.message))
async def _search_profile_mailing_error(message: types.Message) -> None:
    """Catches error if user sends message not matching template"""
    await message.answer(mt.INVALID_MAILING_TO_USER)


async def next_profile(
    session: AsyncSession,
    message: types.Message,
    profile_list: list[int],
    user: UserModel,
    state: FSMContext,
):
    """
    Move to next profile in search results.
    Returns to mode menu when search ends, with mode-specific message.
    """
    data = await state.get_data()
    active_chat_id = data.get("active_card_chat_id", message.chat.id)
    active_message_id = data.get("active_card_message_id")
    if active_message_id:
        try:
            await message.bot.edit_message_reply_markup(
                chat_id=active_chat_id,
                message_id=active_message_id,
                reply_markup=None,
            )
        except Exception:
            # The card may already have been edited or removed; advancing still works.
            pass
    else:
        try:
            await message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

    if profile_list:
        profile_list.pop(0)
    profile = None
    while profile_list:
        candidate = await Profile.get(session, profile_list[0])
        if candidate and candidate.is_active and candidate.age >= 18:
            profile = candidate
            break
        profile_list.pop(0)

    if profile:
        await state.update_data(ids=profile_list)
        sent_profile = await send_profile_with_dist(
            user=user,
            profile=profile,
            session=session,
            include_actions=True,
            mode=data.get("current_mode"),
        )
        await state.update_data(
            active_card_chat_id=sent_profile.chat.id,
            active_card_message_id=sent_profile.message_id,
        )
    else:
        # Get current mode from state
        data = await state.get_data()
        current_mode = data.get("current_mode")
        
        # Clear state and show mode-specific empty message
        await state.clear()
        await answer_inline_message(
            message,
            mt.EMPTY_PROFILE_SEARCH(current_mode),
            mode_menu_ikb(),
        )


async def like_profile(
    session: AsyncSession,
    message: types.Message,
    another_user: UserModel,
    mail_text: str | None = None,
    sender_id: int | None = None,
):
    sender_id = sender_id or message.from_user.id
    is_create = await Match.create(session, sender_id, another_user.id, mail_text)

    if is_create:
        matchs_count = len(await Match.get_user_matchs(session, another_user.id))
        if matchs_count == 1 or matchs_count == 2 or matchs_count % 3 == 0:
            await send_user_like_alert(session, another_user)


async def dislike_profile(
    session: AsyncSession,
    message: types.Message,
    another_user: UserModel,
    sender_id: int | None = None,
):
    """
    Records a dislike so this profile doesn't reappear in search immediately.
    Gets recycled back into the search pool after 30 days (see database/services/search.py).
    """
    await Match.create(
        session=session,
        sender_id=sender_id or message.from_user.id,
        receiver_id=another_user.id,
        mail_text=None,
        status=MatchStatus.Rejected,
    )


@dating_router.callback_query(ProfileActionCallback.filter())
async def profile_action_callback(
    callback: types.CallbackQuery,
    callback_data: ProfileActionCallback,
    state: FSMContext,
    user: UserModel,
    session: AsyncSession,
) -> None:
    lock = _profile_action_locks.setdefault(callback.from_user.id, asyncio.Lock())
    async with lock:
        data = await state.get_data()
        profile_ids = data.get("ids", [])
        current_state = await state.get_state()
        allowed_states = {Search.search.state}
        if current_state == Search.message.state:
            # Let the user change their mind from the still-visible profile card.
            allowed_states.add(Search.message.state)
        if (
            current_state not in allowed_states
            or not profile_ids
            or profile_ids[0] != callback_data.profile_id
        ):
            await callback.answer(_("This card has already been handled."))
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
            return

        action = callback_data.action
        if current_state == Search.message.state and action == "message":
            await callback.answer(_("Send your message or cancel it first."))
            return
        if current_state == Search.message.state and action in {"like", "pass", "report"}:
            prompt_id = data.get("message_prompt_message_id")
            if prompt_id:
                try:
                    await callback.message.bot.edit_message_text(
                        chat_id=callback.message.chat.id,
                        message_id=prompt_id,
                        text=mt.CANNCELED_LETTER,
                        reply_markup=None,
                    )
                except Exception:
                    pass
            await state.set_state(Search.search)
            await state.update_data(message_prompt_message_id=None)

        if action in {"like", "pass", "message", "report"}:
            await state.update_data(
                active_card_chat_id=callback.message.chat.id,
                active_card_message_id=callback.message.message_id,
            )
        target = await User.get_with_profile(session, callback_data.profile_id)
        if not target or not target.profile or not target.profile.is_active or target.profile.age < 18:
            await callback.answer(_("Skipping an unavailable profile."))
            await next_profile(session, callback.message, profile_ids, user, state)
            return

        if action == "like":
            await like_profile(
                session, callback.message, target, sender_id=callback.from_user.id
            )
            await callback.answer(_("Liked"))
            await next_profile(session, callback.message, profile_ids, user, state)
            return
        if action == "pass":
            await dislike_profile(
                session, callback.message, target, sender_id=callback.from_user.id
            )
            await callback.answer(_("Passed"))
            await next_profile(session, callback.message, profile_ids, user, state)
            return
        if action == "message":
            await state.set_state(Search.message)
            prompt = await callback.message.answer(
                mt.MAILING_TO_USER,
                reply_markup=message_cancel_ikb(callback_data.profile_id),
            )
            await state.update_data(
                message_prompt_profile_id=callback_data.profile_id,
                message_prompt_message_id=prompt.message_id,
            )
            await callback.answer()
            return
        if action == "message_cancel":
            await state.set_state(Search.search)
            await state.update_data(
                message_prompt_profile_id=None,
                message_prompt_message_id=None,
            )
            await callback.answer(_("Message cancelled"))
            try:
                await callback.message.edit_text(mt.CANNCELED_LETTER, reply_markup=None)
            except Exception:
                pass
            return
        if action == "report":
            await state.update_data(
                report_pending_id=callback_data.profile_id,
                report_reason=None,
            )
            await callback.answer()
            await callback.message.answer(
                mt.COMPLAINT, reply_markup=report_reasons_ikb(callback_data.profile_id)
            )
            return
        if action == "report_reason":
            if data.get("report_pending_id") != callback_data.profile_id:
                await callback.answer(_("That report has expired."), show_alert=True)
                return
            reasons = {
                "inappropriate": _("Inappropriate content"),
                "spam": _("Spam or scam"),
                "harassment": _("Harassment or abuse"),
                "other": _("Other"),
            }
            reason = reasons.get(callback_data.value)
            if not reason:
                await callback.answer(mt.INVALID_OPTION, show_alert=True)
                return
            await state.update_data(report_reason=reason)
            await callback.answer()
            await callback.message.edit_text(
                _("Report reason: <b>{reason}</b>\n\nSubmit this report?").format(reason=reason),
                reply_markup=report_confirmation_ikb(callback_data.profile_id),
            )
            return
        if action == "report_cancel":
            await state.update_data(report_pending_id=None, report_reason=None)
            await callback.answer(_("Report cancelled"))
            await callback.message.edit_text(_("Report cancelled."), reply_markup=None)
            return
        if action == "report_confirm":
            reason = data.get("report_reason")
            if data.get("report_pending_id") != callback_data.profile_id or not reason:
                await callback.answer(_("That report has expired."), show_alert=True)
                return
            await complaint_to_profile(session, user, target, reason)
            await state.update_data(report_pending_id=None, report_reason=None)
            await callback.answer(_("Report submitted"))
            await next_profile(session, callback.message, profile_ids, user, state)
            return

        await callback.answer(mt.INVALID_OPTION, show_alert=True)
