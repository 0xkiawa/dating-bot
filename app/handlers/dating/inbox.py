import html

from aiogram import F, types
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.business.dating_service import send_user_like_alert
from app.business.profile_service import complaint_to_profile, send_profile_with_dist
from app.business.menu_service import answer_inline_message
from app.constans import EFFECTS_DICTIONARY
from app.keyboards.default.base import match_kb
from app.keyboards.default.compleint import compleint_kb
from app.keyboards.inline.menus import mode_menu_ikb
from app.keyboards.inline.match_contact import match_contact_ikb
from app.routers import dating_router
from app.states.default import LikeResponse
from app.text import message_text as mt
from database.models import UserModel
from database.models.match import MatchModel, MatchStatus
from database.services import Match, User
from loader import bot
from utils.time import time_ago


@dating_router.message(StateFilter(None), F.text == "📭")
async def match_archive(
    message: types.Message, state: FSMContext, user: UserModel, session: AsyncSession
) -> None:
    await show_match_archive(message, state, user, session, username=message.from_user.username)


async def show_match_archive(
    message: types.Message,
    state: FSMContext,
    user: UserModel,
    session: AsyncSession,
    username: str | None,
) -> None:
    await state.clear()
    await User.update(session, id=user.id, username=username)
    items = await Match.inbox_items(session, user.id)
    from app.handlers.dating.search import deliver_match_notifications

    await deliver_match_notifications(session)
    current_mode = await User.get_mode(session, user.id)
    if not items:
        await answer_inline_message(message, mt.LIKE_ARCHIVE(current_mode), mode_menu_ikb())
        return
    await state.set_state(LikeResponse.response)
    await state.update_data(inbox_items=items, inbox_index=0)
    await message.answer(mt.ARCHIVE_SEARCH.format(len(items)), reply_markup=match_kb)
    await _show_inbox_item(message, state, user, session, items[0])


@dating_router.callback_query(StateFilter("*"), F.data == "archive")
async def _match_atchive_callback(
    callback: types.CallbackQuery, state: FSMContext, user: UserModel, session: AsyncSession
) -> None:
    """Open the mode-labeled likes and matches archive."""
    await callback.answer()
    await show_match_archive(
        callback.message,
        state,
        user,
        session,
        username=callback.from_user.username,
    )


async def _show_inbox_item(message, state, user, session, item: dict) -> None:
    another_user = await User.get_with_profile(session, item["user_id"])
    if not another_user or not another_user.profile:
        return
    await send_profile_with_dist(
        user=user,
        profile=another_user.profile,
        session=session,
        mode=item["mode"] if item["mode"] != "legacy" else None,
    )
    mode_label = {"fun": "Fun", "dates": "Dates", "friends": "Friends"}.get(
        item["mode"]
    )
    if item["kind"] == "match":
        matched_with = another_user.profile.name
        elapsed = time_ago(item.get("created_at"))
        if mode_label:
            label = f"✅ You matched with {matched_with} in {mode_label} mode {elapsed}.\n"
        else:
            label = (
                f"✅ You matched with {matched_with} {elapsed}.\n"
                "The mode wasn't recorded for this older match.\n"
            )
        label += "Tap below to open their Telegram profile and start chatting."
        await message.answer(label, reply_markup=match_contact_ikb(another_user))
    else:
        label = f"💌 This Like is from {mode_label or 'an earlier mode not recorded'}."
        await message.answer(label)
    if item.get("message"):
        await message.answer(mt.MESSAGE_TO_YOU.format(item["message"]))


@dating_router.message(
    StateFilter(LikeResponse.response), F.text.in_(("❤️", "👎", "💢", "↩️", "🔞", "💰", "🔫"))
)
async def _match_response(
    message: types.Message, state: FSMContext, user: UserModel, session: AsyncSession
) -> None:
    """Respond to a pending Like or browse a mode-labeled match."""
    data = await state.get_data()
    items = data.get("inbox_items", [])
    index = data.get("inbox_index", 0)
    if index >= len(items):
        await state.clear()
        await answer_inline_message(message, mt.EMPTY_PROFILE_SEARCH(), mode_menu_ikb())
        return
    item = items[index]
    another_user = await User.get_with_profile(session, item["user_id"])
    if not another_user or not another_user.profile:
        index += 1
        await state.update_data(inbox_index=index)
        if index < len(items):
            await _show_inbox_item(message, state, user, session, items[index])
        return
    mode = item["mode"]

    if message.text == "❤️":
        if item["kind"] == "like":
            from app.handlers.dating.search import deliver_match_notifications

            _, match_id = await Match.record_decision(
                session, user.id, another_user.id, mode, "like"
            )
            if match_id:
                await deliver_match_notifications(session, match_id)
        elif item["kind"] == "legacy_like":
            match_data = await Match.get(session, user.id, another_user.id)
            if match_data:
                await Match.update(
                    session=session,
                    id=match_data.id,
                    status=MatchStatus.Accepted,
                    is_active=False,
                )
                legacy_match_id = await Match.record_legacy_match(
                    session, user.id, another_user.id, mode=mode
                )
                from app.handlers.dating.search import deliver_match_notifications

                await deliver_match_notifications(session, legacy_match_id)
        else:
            await like_accept(
                session=session,
                user=user,
                another_user=another_user,
                match=None,
                mode=mode,
            )
    elif message.text == "👎":
        if item["kind"] == "like":
            await Match.record_decision(session, user.id, another_user.id, mode, "pass")
        elif item["kind"] == "legacy_like":
            match_data = await Match.get(session, user.id, another_user.id)
            if match_data:
                await Match.update(
                    session=session,
                    id=match_data.id,
                    status=MatchStatus.Rejected,
                    is_active=False,
                )

    elif message.text == "💢":
        await message.answer(mt.COMPLAINT, reply_markup=compleint_kb())
        return
    elif message.text in ("🔞", "💰", "🔫"):
        await message.answer(mt.REPORT_TO_PROFILE, reply_markup=match_kb)
        await complaint_to_profile(
            session=session,
            sender=user,
            receiver=another_user,
            reason=message.text,
        )
    elif message.text == "↩️":
        await message.answer(mt.SEARCH, reply_markup=match_kb)

    index += 1
    await state.update_data(inbox_index=index)
    if index < len(items):
        await _show_inbox_item(message, state, user, session, items[index])
    else:
        await state.clear()
        await answer_inline_message(
            message,
            mt.LIKE_ARCHIVE(await User.get_mode(session, user.id)),
            mode_menu_ikb(),
        )


def generate_user_link(id: int, username: str = None, sender_profile=None, mode: str = None) -> str:
    """
    Генерирует ссылку на пользователя с персонализированным приветствием
    
    Args:
        id: User ID
        username: Username (if available)
        sender_profile: Profile of the person sending the message (for personalization)
        mode: Current mode (fun/dates/friends)
    
    Returns:
        Telegram link with pre-filled personalized message
    """
    # Build personalized intro message
    if sender_profile and mode:
        # Map role to emoji
        role_emoji = {
            'top': '🔝',
            'bottom': '🔽',
            'verse': '🔄'
        }
        role_icon = role_emoji.get(sender_profile.role, '')
        
        # Build the base intro message
        intro = f"Hey! I'm {sender_profile.name} :) We just matched on Conqueer! I'm a {sender_profile.role} {role_icon} based in {sender_profile.city}. Great to meet you! I was looking for {mode}"
        
        # Add hosting info ONLY for fun mode
        if mode == 'fun' and sender_profile.hosting:
            hosting_text = {
                'yes': 'I can host 🏠',
                'no': "I can't host 🚫",
                'airbnb': 'I do Airbnbs 🏨'
            }
            hosting_msg = hosting_text.get(sender_profile.hosting, '')
            if hosting_msg:
                intro += f". BTW, {hosting_msg}"
        
        # Add appropriate emoji based on mode
        mode_emoji = {
            'fun': ' 🔥',
            'dates': ' ❤️', 
            'friends': ' 🤝'
        }
        intro += mode_emoji.get(mode, '')
        
        # URL encode the message
        from urllib.parse import quote
        encoded_intro = quote(intro)
        
        if username:
            # Use username link with pre-filled text
            return f"https://t.me/{username}?text={encoded_intro}"
        else:
            # For users without username, we can't pre-fill, so just return user link
            return f"tg://user?id={id}"
    else:
        # Fallback to simple link
        if username:
            return f"https://t.me/{username}"
        return f"tg://user?id={id}"

async def like_accept(
    session: AsyncSession,
    user: UserModel,
    another_user: UserModel,
    match: MatchModel | None,
    mode: str = None,
):
    effect_id = EFFECTS_DICTIONARY["🎉"]
    if match is None:
        link = generate_user_link(
            id=another_user.id,
            username=another_user.username,
            sender_profile=user.profile,
            mode=mode,
        )
        text = mt.LIKE_ACCEPT(user.language, mode).format(
            link, html.escape(another_user.profile.name)
        )
        try:
            await bot.send_message(
                chat_id=user.id,
                text=text,
                message_effect_id=effect_id,
                parse_mode="HTML",
            )
        except Exception:
            pass
        return
    if match.status == MatchStatus.Accepted:
        # Если изначальный отправитель получил взимный лайк и зашел в inbox
        sender = user
        reciver = another_user
        await Match.update(session=session, id=match.id, is_active=False)

        # Generate link with personalized intro
        link = generate_user_link(
            id=reciver.id, 
            username=reciver.username,
            sender_profile=sender.profile,
            mode=mode
        )
        text = mt.LIKE_ACCEPT(sender.language, mode).format(
            link, html.escape(reciver.profile.name)
        )
        try:
            await bot.send_message(
                chat_id=sender.id, text=text, message_effect_id=effect_id, parse_mode="HTML"
            )
        except:
            ...

    else:
        # Если изначальный отправитель не этот же человек
        sender = another_user
        reciver = user
        await Match.update(session=session, id=match.id, status=MatchStatus.Accepted)
        await send_user_like_alert(session, sender)

        # Generate link with personalized intro
        link = generate_user_link(
            id=sender.id, 
            username=sender.username,
            sender_profile=reciver.profile,
            mode=mode
        )
        text = mt.LIKE_ACCEPT(reciver.language, mode).format(
            link, html.escape(sender.profile.name)
        )
        try:
            await bot.send_message(
                chat_id=reciver.id, text=text, message_effect_id=effect_id, parse_mode="HTML"
            )
        except:
            ...
