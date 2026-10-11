from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.filters.kb_filter import BrowseFilterCallback
from loader import _


def hosting_filter_ikb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=_("🏠 Host"),
        callback_data=BrowseFilterCallback(step="hosting", value="yes"),
    )
    builder.button(
        text=_("🚫 Can't Host"),
        callback_data=BrowseFilterCallback(step="hosting", value="no"),
    )
    builder.button(
        text=_("🏨 Airbnb"),
        callback_data=BrowseFilterCallback(step="hosting", value="airbnb"),
    )
    builder.button(
        text=_("👁️ See All"),
        callback_data=BrowseFilterCallback(step="hosting", value="all"),
    )
    builder.button(
        text=_("⬅️ Back"),
        callback_data=BrowseFilterCallback(step="back", value="mode_menu"),
    )
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def role_filter_ikb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=_("🍆 Tops"),
        callback_data=BrowseFilterCallback(step="role", value="top"),
    )
    builder.button(
        text=_("🍑 Bottoms"),
        callback_data=BrowseFilterCallback(step="role", value="bottom"),
    )
    builder.button(
        text=_("🍆🍑💦 Verse"),
        callback_data=BrowseFilterCallback(step="role", value="verse"),
    )
    builder.button(
        text=_("👬 Everyone"),
        callback_data=BrowseFilterCallback(step="role", value="all"),
    )
    builder.button(
        text=_("⬅️ Back"),
        callback_data=BrowseFilterCallback(step="back", value="hosting"),
    )
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def age_range_ikb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for label, value in (
        ("18-25", "18_25"),
        ("26-35", "26_35"),
        ("36-45", "36_45"),
        ("46+", "46_plus"),
        (_("Custom"), "custom"),
        (f"✅ {_('Use Default Matching')}", "default"),
    ):
        builder.button(
            text=label,
            callback_data=BrowseFilterCallback(step="age", value=value),
        )
    builder.button(
        text=_("⬅️ Back"),
        callback_data=BrowseFilterCallback(step="back", value="role"),
    )
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()


def custom_age_ikb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=_("⬅️ Back"),
        callback_data=BrowseFilterCallback(step="back", value="age"),
    )
    return builder.as_markup()
