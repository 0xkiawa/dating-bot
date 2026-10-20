import asyncio
import html
from datetime import datetime, timedelta, timezone

from aiogram import F, types
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardRemove
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

import app.filters.create_profile_filtres as filters
from app.business.dating_service import send_user_like_alert
from app.business.menu_service import answer_inline_message
from app.business.profile_service import (
    complaint_to_profile,
    send_discovery_profile,
    send_shared_discovery_profile,
)
from app.filters.kb_filter import ProfileActionCallback
from app.keyboards.inline.menus import mode_menu_ikb
from app.keyboards.inline.match_contact import match_contact_ikb
from app.keyboards.inline.profile_actions import (
    message_cancel_ikb,
    report_confirmation_ikb,
    report_reasons_ikb,
)
from app.routers import dating_router
from app.states.default import Search
from app.text import message_text as mt
from database.models import UserBlockModel, UserModel
from database.services import Match, Profile, User
from database.services.share import consume_pending_shared_view
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
    current_mode = data.get("current_mode")
    shared_card = data.get("shared_card_id") == profile_list[0]
    interaction_mode = (
        data.get("shared_card_mode") or (another_user.current_mode if another_user else None)
        if shared_card
        else current_mode
    )
    if (
        not another_user
        or not another_user.profile
        or not another_user.profile.is_active
        or another_user.profile.age < 18
        or not interaction_mode
        or (not shared_card and await User.get_mode(session, user.id) != current_mode)
        or another_user.current_mode != interaction_mode
    ):
        await next_profile(session, message, profile_list, user, state)
        return

    if message.text == "❤️":
        await like_profile(
            session=session,
            message=message,
            another_user=another_user,
            mode=interaction_mode,
        )
    elif message.text == "👎":
        await dislike_profile(
            session=session,
            message=message,
            another_user=another_user,
            mode=interaction_mode,
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
    current_mode = data.get("current_mode")
    shared_card = data.get("shared_card_id") == profile_list[0]
    interaction_mode = (
        data.get("shared_card_mode") or (another_user.current_mode if another_user else None)
        if shared_card
        else current_mode
    )
    if (
        not another_user
        or not another_user.profile
        or not another_user.profile.is_active
        or another_user.profile.age < 18
        or not interaction_mode
        or (not shared_card and await User.get_mode(session, user.id) != current_mode)
        or another_user.current_mode != interaction_mode
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
    current_mode = data.get("current_mode")
    shared_card = data.get("shared_card_id") == profile_list[0]
    interaction_mode = (
        data.get("shared_card_mode") or (another_user.current_mode if another_user else None)
        if shared_card
        else current_mode
    )
    if (
        not another_user
        or not another_user.profile
        or not another_user.profile.is_active
        or another_user.profile.age < 18
        or not interaction_mode
        or (not shared_card and await User.get_mode(session, user.id) != current_mode)
        or another_user.current_mode != interaction_mode
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
        mode=interaction_mode,
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
    advance_current: bool = True,
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

    if advance_current and profile_list:
        profile_list.pop(0)
    profile = None
    current_mode = data.get("current_mode")
    shared_card_id = data.get("shared_card_id")
    while profile_list:
        candidate = await Profile.get(session, profile_list[0])
        candidate_user = await User.get_with_profile(session, profile_list[0])
        if profile_list[0] == shared_card_id:
            if (
                candidate
                and candidate_user
                and candidate.is_active
                and candidate.age >= 18
                and candidate_user.current_mode == data.get("shared_card_mode")
            ):
                profile = candidate
                break
            profile_list.pop(0)
            continue
        if (
            candidate
            and candidate_user
            and candidate.is_active
            and candidate.age >= 18
            and current_mode
            and candidate_user.current_mode == current_mode
            and await User.get_mode(session, user.id) == current_mode
        ):
            profile = candidate
            break
        profile_list.pop(0)

    sent_profile = None
    while profile:
        if profile.id == shared_card_id:
            try:
                sent_profile = await send_shared_discovery_profile(
                    user=user,
                    target_id=profile.id,
                    pending_id=data.get("shared_pending_id"),
                    session=session,
                )
            except Exception:
                # Keep the pending row retryable; continue the current search.
                sent_profile = None
            if sent_profile:
                await consume_pending_shared_view(
                    session, data.get("shared_pending_id")
                )
        else:
            sent_profile = await send_discovery_profile(
                user=user,
                profile=profile,
                session=session,
                mode=current_mode,
                filters=data,
            )
        if sent_profile:
            break
        profile_list.pop(0)
        profile = None
        while profile_list:
            candidate_user = await User.get_with_profile(session, profile_list[0])
            candidate = candidate_user.profile if candidate_user else None
            if (
                candidate
                and candidate.is_active
                and candidate.age >= 18
                and candidate_user.current_mode == current_mode
                and await User.get_mode(session, user.id) == current_mode
            ):
                profile = candidate
                break
            profile_list.pop(0)

    if profile and sent_profile:
        await state.update_data(ids=profile_list)
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
    mode: str | None = None,
):
    sender_id = sender_id or message.from_user.id
    mode = mode or await User.get_mode(session, sender_id)
    is_create, match_id = await Match.record_decision(
        session, sender_id, another_user.id, mode, "like", mail_text
    )

    if match_id:
        await deliver_match_notifications(session, match_id)
    elif is_create:
        matchs_count = len(await Match.get_user_matchs(session, another_user.id))
        if matchs_count == 1 or matchs_count == 2 or matchs_count % 3 == 0:
            await send_user_like_alert(session, another_user)


async def dislike_profile(
    session: AsyncSession,
    message: types.Message,
    another_user: UserModel,
    sender_id: int | None = None,
    mode: str | None = None,
):
    actor_id = sender_id or message.from_user.id
    mode = mode or await User.get_mode(session, actor_id)
    await Match.record_decision(
        session=session,
        actor_id=actor_id,
        target_id=another_user.id,
        mode=mode,
        decision="pass",
    )


async def deliver_match_notifications(session: AsyncSession, match_id: int | None = None) -> None:
    """Drain the per-recipient outbox; failed Telegram sends remain retryable."""
    from sqlalchemy import select

    from app.constans import EFFECTS_DICTIONARY
    from database.models.match import MatchNotificationModel, PairMatchModel
    from loader import bot

    query = select(MatchNotificationModel).where(MatchNotificationModel.delivered_at.is_(None))
    if match_id:
        query = query.where(MatchNotificationModel.match_id == match_id)
    notifications = (await session.scalars(query.order_by(MatchNotificationModel.id))).all()
    for notification in notifications:
        claimed = await session.execute(
            update(MatchNotificationModel)
            .where(
                MatchNotificationModel.id == notification.id,
                MatchNotificationModel.delivered_at.is_(None),
                or_(
                    MatchNotificationModel.claimed_at.is_(None),
                    MatchNotificationModel.claimed_at
                    < datetime.now(timezone.utc) - timedelta(minutes=5),
                ),
            )
            .values(claimed_at=datetime.now(timezone.utc))
        )
        await session.commit()
        if claimed.rowcount != 1:
            continue
        match = await session.get(PairMatchModel, notification.match_id)
        if not match:
            continue
        recipient = await User.get_with_profile(session, notification.recipient_id)
        other_id = (
            match.user_high_id
            if notification.recipient_id == match.user_low_id
            else match.user_low_id
        )
        other = await User.get_with_profile(session, other_id)
        if not recipient or not other or not other.profile:
            continue
        mode_label = {"fun": "Fun", "dates": "Dates", "friends": "Friends"}.get(
            match.mode, "previous mode"
        )
        other_username = (other.username or "").lstrip("@")
        contact_note = (
            f"\nTelegram: @{html.escape(other_username)}"
            if other_username
            else "\nThey don't have a public Telegram username. The button opens their "
            "Telegram profile if their privacy settings allow it."
        )
        try:
            await bot.send_message(
                chat_id=recipient.id,
                text=f"🎉 <b>It's a match in {mode_label}!</b>\n\n"
                f"You and {html.escape(other.profile.name)} liked each other.\n\n"
                f"You can contact each other on Telegram now.{contact_note}",
                message_effect_id=EFFECTS_DICTIONARY["🎉"],
                parse_mode="HTML",
                reply_markup=match_contact_ikb(other),
            )
            await session.execute(
                update(MatchNotificationModel)
                .where(MatchNotificationModel.id == notification.id)
                .values(delivered_at=datetime.now(timezone.utc), claimed_at=None)
            )
        except Exception:
            await session.execute(
                update(MatchNotificationModel)
                .where(MatchNotificationModel.id == notification.id)
                .values(attempts=MatchNotificationModel.attempts + 1, claimed_at=None)
            )
        await session.commit()


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

        current_mode = data.get("current_mode")
        shared_card = data.get("shared_card_id") == callback_data.profile_id
        if not current_mode or (
            not shared_card and await User.get_mode(session, user.id) != current_mode
        ):
            await callback.answer(
                _("Your active mode changed. Start discovery again."), show_alert=True
            )
            await state.clear()
            return

        action = callback_data.action
        if current_state == Search.message.state and action == "message":
            await callback.answer(_("Send your message or cancel it first."))
            return
        if current_state == Search.message.state and action in {"like", "pass", "report", "block"}:
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

        if action in {"like", "pass", "message", "report", "block"}:
            await state.update_data(
                active_card_chat_id=callback.message.chat.id,
                active_card_message_id=callback.message.message_id,
            )
        target = await User.get_with_profile(session, callback_data.profile_id)
        interaction_mode = (
            data.get("shared_card_mode") or (target.current_mode if target else None)
            if shared_card
            else current_mode
        )
        blocked = (
            await session.scalar(
                select(UserBlockModel.id).where(
                    or_(
                        (UserBlockModel.blocker_id == user.id)
                        & (UserBlockModel.blocked_id == callback_data.profile_id),
                        (UserBlockModel.blocker_id == callback_data.profile_id)
                        & (UserBlockModel.blocked_id == user.id),
                    )
                )
            )
            if shared_card
            else False
        )
        if (
            not target
            or not target.profile
            or not target.profile.is_active
            or target.profile.age < 18
            or target.current_mode != interaction_mode
            or target.status == 0
            or blocked
        ):
            await callback.answer(_("Skipping an unavailable profile."))
            await next_profile(session, callback.message, profile_ids, user, state)
            return

        if action == "like":
            await like_profile(
                session,
                callback.message,
                target,
                sender_id=callback.from_user.id,
                mode=interaction_mode,
            )
            await callback.answer(_("Liked"))
            await next_profile(session, callback.message, profile_ids, user, state)
            return
        if action == "pass":
            await dislike_profile(
                session,
                callback.message,
                target,
                sender_id=callback.from_user.id,
                mode=interaction_mode,
            )
            await callback.answer(_("Passed"))
            await next_profile(session, callback.message, profile_ids, user, state)
            return
        if action == "block":
            await User.block(session, user.id, target.id)
            await callback.answer(_("Blocked"))
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
