from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.filters.kb_filter import ProfileActionCallback
from loader import _


def profile_actions_ikb(
    profile_id: int,
    navigation_buttons: list[InlineKeyboardButton] | None = None,
) -> InlineKeyboardMarkup:
    """Combine carousel controls and swipe actions on the profile card."""
    rows = []
    if navigation_buttons:
        rows.append(navigation_buttons)

    rows.append(
        [
            InlineKeyboardButton(
                text=f"❤️ {_('Like')}",
                callback_data=ProfileActionCallback(
                    action="like", profile_id=profile_id, value=""
                ).pack(),
            ),
            InlineKeyboardButton(
                text=f"👎 {_('Pass')}",
                callback_data=ProfileActionCallback(
                    action="pass", profile_id=profile_id, value=""
                ).pack(),
            ),
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text=f"💬 {_('Message')}",
                callback_data=ProfileActionCallback(
                    action="message", profile_id=profile_id, value=""
                ).pack(),
            ),
            InlineKeyboardButton(
                text=f"🚩 {_('Report')}",
                callback_data=ProfileActionCallback(
                    action="report", profile_id=profile_id, value=""
                ).pack(),
            ),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def report_reasons_ikb(profile_id: int) -> InlineKeyboardMarkup:
    reasons = (
        ("inappropriate", _("Inappropriate content")),
        ("spam", _("Spam or scam")),
        ("harassment", _("Harassment or abuse")),
        ("other", _("Other")),
    )
    rows = [
        [
            InlineKeyboardButton(
                text=label,
                callback_data=ProfileActionCallback(
                    action="report_reason", profile_id=profile_id, value=value
                ).pack(),
            )
        ]
        for value, label in reasons
    ]
    rows.append(
        [
            InlineKeyboardButton(
                text=f"⬅️ {_('Cancel')}",
                callback_data=ProfileActionCallback(
                    action="report_cancel", profile_id=profile_id, value=""
                ).pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def report_confirmation_ikb(profile_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🚩 {_('Submit report')}",
                    callback_data=ProfileActionCallback(
                        action="report_confirm", profile_id=profile_id, value=""
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text=f"⬅️ {_('Cancel')}",
                    callback_data=ProfileActionCallback(
                        action="report_cancel", profile_id=profile_id, value=""
                    ).pack(),
                ),
            ]
        ]
    )


def message_cancel_ikb(profile_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"⬅️ {_('Cancel message')}",
                    callback_data=ProfileActionCallback(
                        action="message_cancel", profile_id=profile_id, value=""
                    ).pack(),
                )
            ]
        ]
    )
