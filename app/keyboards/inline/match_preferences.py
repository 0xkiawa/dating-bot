from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.filters.kb_filter import MatchPreferenceCallback
from loader import _


INTERESTS = (
    ("travel", _("Travel")),
    ("food", _("Food")),
    ("music", _("Music")),
    ("fitness", _("Fitness")),
    ("movies", _("Movies")),
    ("books", _("Books")),
    ("art", _("Art")),
    ("gaming", _("Gaming")),
    ("outdoors", _("Outdoors")),
    ("nightlife", _("Nightlife")),
    ("cooking", _("Cooking")),
    ("pets", _("Pets")),
)

BODY_TYPES = (
    ("slim", _("Slim")),
    ("athletic", _("Athletic")),
    ("average", _("Average")),
    ("muscular", _("Muscular")),
    ("stocky", _("Stocky")),
    ("chubby", _("Chubby")),
    ("thick", _("Thick")),
    ("femme", _("Femme")),
)
BODY_TYPE_LABELS = dict(BODY_TYPES)

INTENTS = {
    "open": _("Open to possibilities"),
    "long_term": _("Long-term dating"),
    "casual": _("Casual dating"),
}


def preferences_text(profile) -> str:
    intent = INTENTS.get(profile.dating_intent or "open", INTENTS["open"])
    body_type = BODY_TYPE_LABELS.get(profile.body_type, _("Not selected"))
    preferred_body_types = [
        label
        for key, label in BODY_TYPES
        if key in (profile.preferred_body_types or [])
    ]
    body_preferences = ", ".join(preferred_body_types) or _("No preference")
    selected_interests = profile.interests or []
    interest_labels = [label for key, label in INTERESTS if key in selected_interests]
    interests = ", ".join(interest_labels) if interest_labels else _("Not selected")

    return _(
        "<b>Match preferences</b>\n\n"
        "My body type: {body_type}\n"
        "I'm into: {body_preferences}\n"
        "Interests: {interests}\n\n"
        "Dating intention: {intent}\n\n"
        "Shared interests and body type preferences help rank compatible profiles."
    ).format(
        intent=intent,
        body_type=body_type,
        body_preferences=body_preferences,
        interests=interests,
    )


def preferences_ikb(profile) -> InlineKeyboardMarkup:
    interest_count = len(profile.interests or [])
    body_type_label = BODY_TYPE_LABELS.get(profile.body_type, _("Set body type"))
    preferred_body_type_count = len(profile.preferred_body_types or [])
    intent_label = INTENTS.get(profile.dating_intent or "open", INTENTS["open"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"👤 {_('My body type')}: {body_type_label}",
                    callback_data=MatchPreferenceCallback(
                        action="body_type", value=""
                    ).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"💞 {_('I’m into')} ({preferred_body_type_count})",
                    callback_data=MatchPreferenceCallback(
                        action="body_preferences", value=""
                    ).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"✨ {_('Interests')} ({interest_count}/5)",
                    callback_data=MatchPreferenceCallback(action="interests", value="").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"💜 {intent_label}",
                    callback_data=MatchPreferenceCallback(action="intents", value="").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"⬅️ {_('Back to menu')}",
                    callback_data=MatchPreferenceCallback(action="back", value="").pack(),
                )
            ],
        ]
    )


def intent_preferences_ikb(profile) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=("✅ " if profile.dating_intent == value else "") + label,
                callback_data=MatchPreferenceCallback(
                    action="set_intent", value=value
                ).pack(),
            )
        ]
        for value, label in INTENTS.items()
    ]
    rows.append(_back_to_preferences_button())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def interests_preferences_ikb(profile) -> InlineKeyboardMarkup:
    selected = set(profile.interests or [])
    rows = []
    for index in range(0, len(INTERESTS), 2):
        rows.append(
            [
                InlineKeyboardButton(
                    text=("✅ " if value in selected else "") + label,
                    callback_data=MatchPreferenceCallback(
                        action="toggle_interest", value=value
                    ).pack(),
                )
                for value, label in INTERESTS[index : index + 2]
            ]
        )
    rows.append(_back_to_preferences_button())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def body_type_preferences_ikb(profile) -> InlineKeyboardMarkup:
    rows = []
    for index in range(0, len(BODY_TYPES), 2):
        rows.append(
            [
                InlineKeyboardButton(
                    text=("✅ " if profile.body_type == value else "") + label,
                    callback_data=MatchPreferenceCallback(
                        action="set_body_type", value=value
                    ).pack(),
                )
                for value, label in BODY_TYPES[index : index + 2]
            ]
        )
    rows.append(_back_to_preferences_button())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def preferred_body_types_ikb(profile) -> InlineKeyboardMarkup:
    selected = set(profile.preferred_body_types or [])
    rows = []
    for index in range(0, len(BODY_TYPES), 2):
        rows.append(
            [
                InlineKeyboardButton(
                    text=("✅ " if value in selected else "") + label,
                    callback_data=MatchPreferenceCallback(
                        action="toggle_body_preference", value=value
                    ).pack(),
                )
                for value, label in BODY_TYPES[index : index + 2]
            ]
        )
    rows.append(_back_to_preferences_button())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _back_to_preferences_button() -> list[InlineKeyboardButton]:
    return [
        InlineKeyboardButton(
            text=f"⬅️ {_('Back')}",
            callback_data=MatchPreferenceCallback(action="open", value="").pack(),
        )
    ]
