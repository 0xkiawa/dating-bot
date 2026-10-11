from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.filters.kb_filter import (
    MainMenuCallback,
    ModeConfirmCallback,
    ModeMenuCallback,
    ModeSelectionCallback,
)
from loader import _


def main_menu_ikb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👤", callback_data=MainMenuCallback(action="profile"))
    builder.button(text="✉️", callback_data=MainMenuCallback(action="invite"))
    builder.button(text="🎭", callback_data=MainMenuCallback(action="modes"))
    builder.adjust(2, 1)
    return builder.as_markup()


def welcome_menu_ikb() -> InlineKeyboardMarkup:
    """Inline actions shown to users who have not created a profile yet."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"👤 {_('Create a profile')}",
        callback_data=MainMenuCallback(action="create_profile"),
    )
    builder.button(
        text=f"🎭 {_('Enter Mode')}",
        callback_data=MainMenuCallback(action="welcome_modes"),
    )
    builder.adjust(1)
    return builder.as_markup()


def main_menu_back_ikb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Back", callback_data=MainMenuCallback(action="menu"))
    return builder.as_markup()


def mode_selection_ikb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"🍆👅🍑💦 {_('Fun Mode')}",
        callback_data=ModeSelectionCallback(mode="fun"),
    )
    builder.button(
        text=f"❤️🥂 {_('Dating Mode')}",
        callback_data=ModeSelectionCallback(mode="dates"),
    )
    builder.button(
        text=f"🤝 {_('Friends Mode')}",
        callback_data=ModeSelectionCallback(mode="friends"),
    )
    builder.button(text="⬅️ Back", callback_data=MainMenuCallback(action="menu"))
    builder.adjust(1)
    return builder.as_markup()


def mode_confirm_ikb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"✅ {_('Yes, Switch')}",
        callback_data=ModeConfirmCallback(switch=True),
    )
    builder.button(
        text=f"❌ {_('No, Stay')}",
        callback_data=ModeConfirmCallback(switch=False),
    )
    builder.adjust(2)
    return builder.as_markup()


def mode_menu_ikb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔍", callback_data=ModeMenuCallback(action="browse"))
    builder.button(text="📭", callback_data=ModeMenuCallback(action="likes"))
    builder.button(text="🎂", callback_data=ModeMenuCallback(action="age"))
    builder.button(text="🏠", callback_data=ModeMenuCallback(action="hosting"))
    builder.button(text="⬅️ Back", callback_data=ModeMenuCallback(action="back"))
    builder.button(text="💤", callback_data=ModeMenuCallback(action="menu"))
    builder.adjust(2, 2, 2)
    return builder.as_markup()
