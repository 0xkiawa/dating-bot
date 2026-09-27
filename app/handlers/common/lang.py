from aiogram import types
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.inline.lang import LangCallback, lang_ikb
from app.routers import common_router
from app.text import message_text as mt
from database.models import UserModel
from database.services import User
from loader import i18n


@common_router.message(Command("language"))
@common_router.message(Command("lang"))
async def _lang(message: types.Message) -> None:
    """Show supported languages and let the user change their preference."""
    await message.answer(mt.CHANGE_LANG, reply_markup=lang_ikb())


@common_router.callback_query(LangCallback.filter())
async def _change_lang(
    callback: types.CallbackQuery,
    callback_data: LangCallback,
    user: UserModel,
    session: AsyncSession,
) -> None:
    """Save the selected locale and confirm the change in that locale."""
    language = callback_data.lang
    if language not in i18n.available_locales:
        await callback.answer(mt.UNSUPPORTED_LANGUAGE, show_alert=True)
        return

    await User.update(session=session, id=user.id, language=language)
    await callback.message.edit_text(mt.DONE_CHANGE_LANG(language))
    await callback.answer()
