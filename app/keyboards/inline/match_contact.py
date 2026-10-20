from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from database.models import UserModel


def match_contact_ikb(user: UserModel) -> InlineKeyboardMarkup:
    """Link a confirmed match to the other user's Telegram account."""
    username = (user.username or "").lstrip("@")
    contact_url = (
        f"https://t.me/{username}"
        if username
        else f"tg://user?id={user.id}"
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💬 Message your match", url=contact_url)]
        ]
    )
