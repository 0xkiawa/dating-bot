from aiogram import types
from aiogram.types import InlineKeyboardMarkup

from app.keyboards.inline.menus import main_menu_ikb
from app.text import message_text as mt
from loader import bot


async def menu(chat_id: int) -> None:
    """Send the main menu with its inline keyboard attached to the response."""
    await bot.send_message(
        chat_id=chat_id,
        text=mt.MENU,
        reply_markup=main_menu_ikb(),
    )


async def answer_inline_message(
    message: types.Message,
    text: str,
    reply_markup: InlineKeyboardMarkup,
) -> types.Message:
    """Send inline navigation with the keyboard attached in the initial request."""
    return await message.answer(text=text, reply_markup=reply_markup)
