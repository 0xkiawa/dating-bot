from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.locales import normalize_locale
from loader import _


def check_archive_ikb(language: str) -> InlineKeyboardMarkup:
    ikb = InlineKeyboardMarkup(
        resize_keyboard=True,
        inline_keyboard=[
            [InlineKeyboardButton(text=_("View", locale=normalize_locale(language)), callback_data="archive")],
        ],
    )
    return ikb


