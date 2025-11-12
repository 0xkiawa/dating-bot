import html

from aiogram import F, types
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.business.dating_service import send_user_like_alert
from app.business.profile_service import complaint_to_profile, send_profile_with_dist
from app.constans import EFFECTS_DICTIONARY
from app.handlers.common.start import start_command
from app.keyboards.default.base import match_kb, mode_menu_kb
from app.keyboards.default.compleint import compleint_kb
from app.routers import dating_router
from app.states.default import LikeResponse
from app.text import message_text as mt
from database.models import UserModel
from database.models.match import MatchModel, MatchStatus
from database.services import Match, Profile, User
from loader import bot


async def _send_mutual_like_notifications(session: AsyncSession, user: UserModel) -> None:
    """
    Отправляет уведомления о взаимных лайках для матчей со статусом Accepted,
    которые исходят от пользователя
    """
    effect_id = EFFECTS_DICTIONARY["🎉"]

    # Найти все матчи со статусом Accepted, где пользователь является отправителем
    result = await session.execute(
        select(MatchModel)
        .where(MatchModel.sender_id == user.id)
        .where(MatchModel.status == MatchStatus.Accepted)
        .where(MatchModel.is_active == True)
    )
    accepted_matches = result.scalars().all()
    for match in accepted_matches:
        try:
            # Получаем профиль получателя
            receiver = await User.get_with_profile(session, match.receiver_id)
            await send_profile_with_dist(session=session, user=user, profile=receiver.profile)
            if receiver and receiver.profile:
                # Генерируем ссылку и текст
                link = generate_user_link(id=receiver.id, username=receiver.username)
                text = mt.LIKE_ACCEPT(user.language).format(
                    link, html.escape(receiver.profile.name)
                )

                # Отправляем уведомление
                await bot.send_message(
                    chat_id=user.id, text=text, message_effect_id=effect_id, parse_mode="HTML"
                )

                # Деактивируем матч, чтобы не отправлять уведомление повторно
                await Match.update(session=session, id=match.id, is_active=False)

        except Exception as e:
            pass


@dating_router.message(StateFilter(None), F.text == "📭")
async def match_archive(
    message: types.Message, state: FSMContext, user: UserModel, session: AsyncSession
) -> None:
    """Архив лайков анкеты пользовтеля - FILTERED BY CURRENT MODE"""
    await state.set_state(LikeResponse.response)
    await User.update(
        session,
        id=user.id,
        username=message.from_user.username,
    )  # needs to be redone

    # Get current mode
    current_mode = await User.get_mode(session, user.id)
    
    if not current_mode:
        await message.answer("Please select a mode first: /fun, /dates, or /friends")
        return

    # Проверяем и отправляем уведомления о взаимных лайках
    await _send_mutual_like_notifications(session, user)

    # Get matches filtered by current mode
    if liker_ids := await Match.get_user_matchs_by_mode(session, message.from_user.id, current_mode):
        text = mt.ARCHIVE_SEARCH.format(len(liker_ids))
        await message.answer(text=text, reply_markup=match_kb)

        await state.update_data(ids=liker_ids, current_mode=current_mode)
        profile = await Profile.get(session, liker_ids[0])
        match_data = await Match.get(session, user.id, profile.id)
        await send_profile_with_dist(user=user, profile=profile, session=session)
        if match_data and match_data.message:
            await message.answer(mt.MESSAGE_TO_YOU.format(match_data.message))
    else:
        # Show mode-specific empty message
        await message.answer(mt.LIKE_ARCHIVE(current_mode), reply_markup=mode_menu_kb)


@dating_router.callback_query(StateFilter("*"), F.data == "archive")
async def _match_atchive_callback(
    callback: types.CallbackQuery, state: FSMContext, user: UserModel, session: AsyncSession
) -> None:
    """Архив лайков анкеты пользовтеля - FILTERED BY CURRENT MODE"""
    await state.set_state(LikeResponse.response)
    await User.update(
        session,
        id=user.id,
        username=callback.from_user.username,
    )  # needs to be redone
    await callback.message.answer(text=mt.SEARCH, reply_markup=match_kb)
    await callback.answer()

    # Get current mode
    current_mode = await User.get_mode(session, user.id)
    
    if not current_mode:
        await callback.message.answer("Please select a mode first: /fun, /dates, or /friends")
        return

    # Проверяем и отправляем уведомления о взаимных лайках
    await _send_mutual_like_notifications(session, user)

    # Get matches filtered by current mode
    if liker_ids := await Match.get_user_matchs_by_mode(session, callback.from_user.id, current_mode):
        await state.update_data(ids=liker_ids, current_mode=current_mode)
        profile = await Profile.get(session, liker_ids[0])
        match_data = await Match.get(session, user.id, profile.id)
        await send_profile_with_dist(user=user, profile=profile, session=session)
        if match_data and match_data.message:
            await callback.message.answer(mt.MESSAGE_TO_YOU.format(match_data.message))
    else:
        # Show mode-specific empty message
        await callback.message.answer(mt.LIKE_ARCHIVE(current_mode), reply_markup=mode_menu_kb)


@dating_router.message(
    StateFilter(LikeResponse.response), F.text.in_(("❤️", "👎", "💢", "↩️", "🔞", "💰", "🔫"))
)
async def _match_response(
    message: types.Message, state: FSMContext, user: UserModel, session: AsyncSession
) -> None:
    """'Свайпы' людей которые лайкнули анкету пользователя"""
    data = await state.get_data()
    ids = data.get("ids")
    current_mode = data.get("current_mode")

    another_user = await User.get_with_profile(session, ids[0])
    match_data = await Match.get(session, user.id, another_user.id)

    if message.text == "❤️":
        """Отправка пользователю который ответил на лайк"""
        await like_accept(session=session, user=user, another_user=another_user, match=match_data)
    elif message.text == "👎":
        pass
        await Match.update(
            session=session, id=match_data.id, status=MatchStatus.Rejected, is_active=False
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

    ids.pop(0)
    await state.update_data(ids=ids)
    if ids:
        profile = await Profile.get(session, ids[0])
        match_data = await Match.get(session, user.id, profile.id)
        await send_profile_with_dist(user=user, profile=profile, session=session)
        if match_data and match_data.message:
            await message.answer(mt.MESSAGE_TO_YOU.format(match_data.message))
    else:
        # Show mode-specific empty message and return to mode menu
        await message.answer(mt.EMPTY_PROFILE_SEARCH(current_mode), reply_markup=mode_menu_kb)


def generate_user_link(id: int, username: str = None) -> str:
    """
    Генерирует ссылку на пользователя
    Если указан username, создается ссылка https://t.me/username,
    иначе используется tg://user?id=id.
    """
    if username:
        return f"https://t.me/{username}"
    return f"tg://user?id={id}"


async def like_accept(
    session: AsyncSession, user: UserModel, another_user: UserModel, match: MatchModel
):
    effect_id = EFFECTS_DICTIONARY["🎉"]
    if match.status == MatchStatus.Accepted:
        # Если изначальный отправитель получил взимный лайк и зашел в inbox
        sender = user
        reciver = another_user
        await Match.update(session=session, id=match.id, is_active=False)

        link = generate_user_link(id=reciver.id, username=reciver.username)
        text = mt.LIKE_ACCEPT(sender.language).format(link, html.escape(reciver.profile.name))
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

        link = generate_user_link(id=sender.id, username=sender.username)
        text = mt.LIKE_ACCEPT(reciver.language).format(link, html.escape(sender.profile.name))
        try:
            await bot.send_message(
                chat_id=reciver.id, text=text, message_effect_id=effect_id, parse_mode="HTML"
            )
        except:
            ...