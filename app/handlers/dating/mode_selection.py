from aiogram import F, types
from aiogram.filters import Filter
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.default.base import mode_menu_kb, mode_selection_kb
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


@dating_router.message(F.text == "🎭")
async def enter_mode_handler(
    message: types.Message, state: FSMContext, user: UserModel, session: AsyncSession
) -> None:
    await message.answer(mt.SELECT_MODE, reply_markup=mode_selection_kb())


@dating_router.message(ModeSelectionFilter())
async def mode_selection_handler(
    message: types.Message,
    state: FSMContext,
    user: UserModel,
    session: AsyncSession,
    selected_mode: str,
) -> None:
    current_mode = await User.get_mode(session, user.id)
    if not current_mode:
        await activate_mode(message, state, user, session, selected_mode)
        return
    if current_mode == selected_mode:
        await show_mode_menu(message, selected_mode)
        return

    await state.update_data(pending_mode=selected_mode)
    confirm_text = mt.MODE_SWITCH_CONFIRM(current_mode, selected_mode)
    from app.keyboards.default.base import mode_confirm_kb
    await message.answer(confirm_text, reply_markup=mode_confirm_kb())


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

    mode_messages = {
        "fun": mt.MODE_FUN_ACTIVATED,
        "dates": mt.MODE_DATES_ACTIVATED,
        "friends": mt.MODE_FRIENDS_ACTIVATED,
    }
    await message.answer(mode_messages[mode])
    await show_mode_menu(message, mode)


async def show_mode_menu(message: types.Message, mode: str) -> None:
    mode_menus = {
        "fun": mt.MODE_FUN_MENU,
        "dates": mt.MODE_DATES_MENU,
        "friends": mt.MODE_FRIENDS_MENU,
    }
    await message.answer(mode_menus.get(mode, mt.INVALID_OPTION), reply_markup=mode_menu_kb)
