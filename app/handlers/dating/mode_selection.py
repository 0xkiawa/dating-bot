from aiogram import F, types
from aiogram.filters import Filter
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.business.menu_service import answer_inline_message
from app.filters.kb_filter import (
    MainMenuCallback,
    ModeConfirmCallback,
    ModeSelectionCallback,
)
from app.keyboards.inline.menus import (
    mode_confirm_ikb,
    mode_menu_ikb,
    mode_selection_ikb,
)
from app.routers import dating_router
from app.text import message_text as mt
from database.models import UserModel
from database.services import User
from loader import _


class ModeSelectionFilter(Filter):
    async def __call__(self, message: types.Message) -> dict | bool:
        choices = {
            f"🍆👅🍑💦 {_('Fun Mode')}": "fun",
            f"❤️🥂 {_('Dating Mode')}": "dates",
            f"🤝 {_('Friends Mode')}": "friends",
        }
        selected_mode = choices.get(message.text)
        return {"selected_mode": selected_mode} if selected_mode else False


def mode_menu_text(mode: str) -> str:
    mode_menus = {
        "fun": mt.MODE_FUN_MENU,
        "dates": mt.MODE_DATES_MENU,
        "friends": mt.MODE_FRIENDS_MENU,
    }
    return mode_menus.get(mode, mt.INVALID_OPTION)


def mode_activated_text(mode: str) -> str:
    mode_messages = {
        "fun": mt.MODE_FUN_ACTIVATED,
        "dates": mt.MODE_DATES_ACTIVATED,
        "friends": mt.MODE_FRIENDS_ACTIVATED,
    }
    return mode_messages[mode]


@dating_router.callback_query(MainMenuCallback.filter(F.action == "modes"))
async def enter_mode_callback(
    callback: types.CallbackQuery, state: FSMContext
) -> None:
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(mt.SELECT_MODE, reply_markup=mode_selection_ikb())


@dating_router.message(F.text == "🎭")
async def enter_mode_handler(
    message: types.Message, state: FSMContext, user: UserModel, session: AsyncSession
) -> None:
    await state.clear()
    await answer_inline_message(message, mt.SELECT_MODE, mode_selection_ikb())


@dating_router.callback_query(ModeSelectionCallback.filter())
async def mode_selection_callback(
    callback: types.CallbackQuery,
    callback_data: ModeSelectionCallback,
    state: FSMContext,
    user: UserModel,
    session: AsyncSession,
) -> None:
    await callback.answer()
    await state.clear()

    selected_mode = callback_data.mode
    if selected_mode not in {"fun", "dates", "friends"}:
        await callback.message.edit_text(mt.INVALID_OPTION, reply_markup=mode_selection_ikb())
        return

    current_mode = await User.get_mode(session, user.id)
    if current_mode == selected_mode and mode_menu_text(selected_mode) in (
        callback.message.text or ""
    ):
        return

    if not current_mode or current_mode == selected_mode:
        if not current_mode and not await User.set_mode(session, user.id, selected_mode):
            await callback.message.edit_text(
                mt.MODE_ACTIVATION_ERROR, reply_markup=mode_selection_ikb()
            )
            return

        menu_text = mode_menu_text(selected_mode)
        if not current_mode:
            menu_text = f"{mode_activated_text(selected_mode)}\n\n{menu_text}"
        await callback.message.edit_text(menu_text, reply_markup=mode_menu_ikb())
        return

    await state.update_data(pending_mode=selected_mode)
    await callback.message.edit_text(
        mt.MODE_SWITCH_CONFIRM(current_mode, selected_mode),
        reply_markup=mode_confirm_ikb(),
    )


@dating_router.callback_query(ModeConfirmCallback.filter())
async def mode_confirmation_callback(
    callback: types.CallbackQuery,
    callback_data: ModeConfirmCallback,
    state: FSMContext,
    user: UserModel,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    pending_mode = data.get("pending_mode")
    if pending_mode not in {"fun", "dates", "friends"}:
        await callback.answer("This selection has expired.", show_alert=True)
        return

    await callback.answer()

    if callback_data.switch:
        if not await User.set_mode(session, user.id, pending_mode):
            await state.clear()
            await callback.message.edit_text(
                mt.MODE_ACTIVATION_ERROR, reply_markup=mode_selection_ikb()
            )
            return

        menu_text = f"{mode_activated_text(pending_mode)}\n\n{mode_menu_text(pending_mode)}"
    else:
        current_mode = await User.get_mode(session, user.id)
        menu_text = f"{mt.MODE_SWITCH_CANCELLED}\n\n{mode_menu_text(current_mode)}"

    await state.clear()
    await callback.message.edit_text(menu_text, reply_markup=mode_menu_ikb())


@dating_router.message(ModeSelectionFilter())
async def mode_selection_handler(
    message: types.Message,
    state: FSMContext,
    user: UserModel,
    session: AsyncSession,
    selected_mode: str,
) -> None:
    """Compatibility path for users who still have a reply keyboard open."""
    current_mode = await User.get_mode(session, user.id)
    if not current_mode:
        await activate_mode(message, state, user, session, selected_mode)
        return
    if current_mode == selected_mode:
        await show_mode_menu(message, selected_mode)
        return

    await state.update_data(pending_mode=selected_mode)
    confirm_text = mt.MODE_SWITCH_CONFIRM(current_mode, selected_mode)
    await answer_inline_message(message, confirm_text, mode_confirm_ikb())


async def activate_mode(
    message: types.Message,
    state: FSMContext,
    user: UserModel,
    session: AsyncSession,
    mode: str,
) -> None:
    if not await User.set_mode(session, user.id, mode):
        await message.answer(mt.MODE_ACTIVATION_ERROR)
        return

    await message.answer(mode_activated_text(mode))
    await show_mode_menu(message, mode)


async def show_mode_menu(message: types.Message, mode: str) -> None:
    await answer_inline_message(message, mode_menu_text(mode), mode_menu_ikb())
