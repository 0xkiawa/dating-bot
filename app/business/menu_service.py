from aiogram import types
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardRemove

from app.keyboards.inline.menus import main_menu_ikb
from app.text import message_text as mt
from loader import bot


async def menu(chat_id: int) -> None:
    """Send the inline main menu and clear any persistent legacy reply keyboard."""
    message = await bot.send_message(
        chat_id=chat_id,
        text=mt.MENU,
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.edit_reply_markup(reply_markup=main_menu_ikb())


async def answer_inline_message(
    message: types.Message,
    text: str,
    reply_markup: InlineKeyboardMarkup,
) -> types.Message:
    """Send inline navigation while removing any persistent reply keyboard."""
    sent = await message.answer(text=text, reply_markup=ReplyKeyboardRemove())
    await sent.edit_reply_markup(reply_markup=reply_markup)
    return sent
