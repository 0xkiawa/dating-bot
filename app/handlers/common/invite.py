from aiogram import F, types
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.utils.deep_linking import create_start_link
from sqlalchemy.ext.asyncio import AsyncSession

from app.filters.kb_filter import MainMenuCallback
from app.keyboards.default.base import return_to_menu_kb
from app.keyboards.inline.menus import main_menu_back_ikb
from app.routers import common_router
from app.text import message_text as mt
from database.models import UserModel
from database.services.referal import Referal
from loader import bot
from utils.base62 import encode_base62


@common_router.message(StateFilter(None), F.text == "✉️")
async def _invite_link_command(
    message: types.Message, user: UserModel, session: AsyncSession
) -> None:
    """Sends a personalized referral link to invite friends.
The link is generated based on the user ID and base62 encoding."""
    text = await _invite_text(message.from_user.id, user, session)
    await message.answer(text, reply_markup=return_to_menu_kb)


@common_router.callback_query(MainMenuCallback.filter(F.action == "invite"))
async def _invite_link_callback(
    callback: types.CallbackQuery,
    user: UserModel,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    await callback.answer()
    await state.clear()
    text = await _invite_text(callback.from_user.id, user, session)
    await callback.message.edit_text(text, reply_markup=main_menu_back_ikb())


async def _invite_text(user_id: int, user: UserModel, session: AsyncSession) -> str:
    user_code: str = encode_base62(user_id)
    url = await create_start_link(bot, f"usr_{user_code}")
    invites_count = await Referal.get_invites_count(session, user.id)
    return mt.INVITE_FRIENDS.format(invites_count, url)
