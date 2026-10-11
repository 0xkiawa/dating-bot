from aiogram import F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.filters.kb_filter import MainMenuCallback, MatchPreferenceCallback
from app.keyboards.inline.match_preferences import (
    AGE_RANGES,
    DISTANCES,
    INTENTS,
    INTERESTS,
    age_preferences_ikb,
    distance_preferences_ikb,
    interests_preferences_ikb,
    intent_preferences_ikb,
    preferences_ikb,
    preferences_text,
)
from app.keyboards.inline.menus import main_menu_ikb, welcome_menu_ikb
from app.routers import dating_router
from app.text import message_text as mt
from database.models import UserModel
from loader import _


@dating_router.message(Command("preferences"))
async def preferences_command(
    message: types.Message,
    state: FSMContext,
    user: UserModel,
) -> None:
    await state.clear()
    if not user.profile:
        await message.answer(mt.NO_PROFILE_FOR_SEARCH, reply_markup=welcome_menu_ikb())
        return
    await message.answer(
        preferences_text(user.profile),
        reply_markup=preferences_ikb(user.profile),
    )


@dating_router.callback_query(MainMenuCallback.filter(F.action == "preferences"))
async def open_preferences_callback(
    callback: types.CallbackQuery,
    state: FSMContext,
    user: UserModel,
) -> None:
    await callback.answer()
    await state.clear()
    await show_preferences(callback.message, user)


async def show_preferences(message: types.Message, user: UserModel) -> None:
    if not user.profile:
        await message.answer(mt.NO_PROFILE_FOR_SEARCH, reply_markup=welcome_menu_ikb())
        return
    await message.edit_text(
        preferences_text(user.profile),
        reply_markup=preferences_ikb(user.profile),
    )


@dating_router.callback_query(MatchPreferenceCallback.filter())
async def match_preference_callback(
    callback: types.CallbackQuery,
    callback_data: MatchPreferenceCallback,
    user: UserModel,
    session: AsyncSession,
) -> None:
    profile = user.profile
    if not profile:
        await callback.answer(mt.NO_PROFILE_FOR_SEARCH, show_alert=True)
        return

    action = callback_data.action
    value = callback_data.value

    if action == "back":
        await callback.answer()
        await callback.message.edit_text(mt.MENU, reply_markup=main_menu_ikb())
        return
    if action == "open":
        await callback.answer()
        await callback.message.edit_text(
            preferences_text(profile), reply_markup=preferences_ikb(profile)
        )
        return
    if action == "ages":
        await callback.answer()
        await callback.message.edit_text(
            _("Choose the age range you want to see:"),
            reply_markup=age_preferences_ikb(profile),
        )
        return
    if action == "distances":
        await callback.answer()
        await callback.message.edit_text(
            _("Choose the maximum distance for matches:"),
            reply_markup=distance_preferences_ikb(),
        )
        return
    if action == "intents":
        await callback.answer()
        await callback.message.edit_text(
            _("What are you looking for in Dating Mode?"),
            reply_markup=intent_preferences_ikb(profile),
        )
        return
    if action == "interests":
        await callback.answer()
        await callback.message.edit_text(
            _("Choose up to five interests. These improve profile ranking:"),
            reply_markup=interests_preferences_ikb(profile),
        )
        return
    if action == "set_age":
        age_range = AGE_RANGES.get(value)
        if age_range is None:
            await callback.answer(_("That age range is unavailable."), show_alert=True)
            return
        profile.preferred_age_min, profile.preferred_age_max = age_range
        await session.commit()
        await callback.answer(_("Age preference saved."))
        await callback.message.edit_text(
            preferences_text(profile), reply_markup=preferences_ikb(profile)
        )
        return
    if action == "set_distance":
        try:
            distance = int(value)
        except ValueError:
            distance = 0
        if distance not in DISTANCES:
            await callback.answer(_("That distance is unavailable."), show_alert=True)
            return
        profile.preferred_distance_km = distance
        await session.commit()
        await callback.answer(_("Distance preference saved."))
        await callback.message.edit_text(
            preferences_text(profile), reply_markup=preferences_ikb(profile)
        )
        return
    if action == "set_intent":
        if value not in INTENTS:
            await callback.answer(_("That dating intention is unavailable."), show_alert=True)
            return
        profile.dating_intent = value
        await session.commit()
        await callback.answer(_("Dating intention saved."))
        await callback.message.edit_text(
            preferences_text(profile), reply_markup=preferences_ikb(profile)
        )
        return
    if action == "toggle_interest":
        valid_interests = {key for key, _label in INTERESTS}
        if value not in valid_interests:
            await callback.answer(_("That interest is unavailable."), show_alert=True)
            return

        selected = list(profile.interests or [])
        if value in selected:
            selected.remove(value)
        elif len(selected) >= 5:
            await callback.answer(_("Choose up to five interests."), show_alert=True)
            return
        else:
            selected.append(value)
        profile.interests = selected
        await session.commit()
        await callback.answer()
        await callback.message.edit_reply_markup(
            reply_markup=interests_preferences_ikb(profile)
        )
        return

    await callback.answer(mt.INVALID_OPTION, show_alert=True)
