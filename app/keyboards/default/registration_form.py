from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from database.models.profile import ProfileModel
from database.models.user import UserModel
from loader import _

from .base import del_kb
from .kb_generator import simple_kb_generator as kb_gen


def create_profile_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(
        resize_keyboard=True,
        keyboard=[
            [
                KeyboardButton(text=_("Create a profile")),
            ],
        ],
    )
    return kb


class RegistrationFormKb:
    @staticmethod
    def role() -> ReplyKeyboardMarkup:
        """Select your role: Top, Bottom, or Verse"""
        kb = ReplyKeyboardMarkup(
            resize_keyboard=True,
            keyboard=[
                [
                    KeyboardButton(text=_("Top")),
                    KeyboardButton(text=_("Bottom")),
                    KeyboardButton(text=_("Verse")),
                ],
            ],
        )
        return kb

    @staticmethod
    def find_role() -> ReplyKeyboardMarkup:
        """Select who you're looking for"""
        kb = ReplyKeyboardMarkup(
            resize_keyboard=True,
            keyboard=[
                [
                    KeyboardButton(text=_("Tops")),
                    KeyboardButton(text=_("Bottoms")),
                ],
                [
                    KeyboardButton(text=_("Verse")),
                    KeyboardButton(text=_("Everyone")),
                ],
            ],
        )
        return kb

    @staticmethod
    def photo(user: UserModel) -> ReplyKeyboardMarkup:
        return RegistrationFormKb.leave_previous(user.profile)

    @staticmethod
    def photo_add() -> ReplyKeyboardMarkup:
        builder = ReplyKeyboardBuilder()
        builder.button(text=_("That's all, save photos"))
        builder.adjust(1)
        return builder.as_markup(resize_keyboard=True)

    @staticmethod
    def age(user: UserModel) -> ReplyKeyboardMarkup:
        try:
            kb = kb_gen([str(user.profile.age)])
        except:
            kb = del_kb
        return kb

    @staticmethod
    def name(user: UserModel) -> ReplyKeyboardMarkup:
        try:
            kb = kb_gen([user.profile.name])
        except:
            kb = del_kb
        return kb

    @staticmethod
    def description(user: UserModel) -> ReplyKeyboardMarkup:
        builder = ReplyKeyboardBuilder()
        if user.profile and user.profile.description:
            builder.button(text=_("Keep previous"))
        builder.button(text=_("Skip"))

        builder.adjust(1)
        return builder.as_markup(resize_keyboard=True)

    @staticmethod
    def hosting() -> ReplyKeyboardMarkup:
        """Select hosting option"""
        kb = ReplyKeyboardMarkup(
            resize_keyboard=True,
            keyboard=[
                [
                    KeyboardButton(text=_("✅ Yes")),
                    KeyboardButton(text=_("❌ No")),
                ],
                [
                    KeyboardButton(text=_("🏨 Airbnb")),
                ],
            ],
        )
        return kb

    @staticmethod
    def hosting_filter() -> ReplyKeyboardMarkup:
        """Filter profiles by hosting preference"""
        kb = ReplyKeyboardMarkup(
            resize_keyboard=True,
            keyboard=[
                [
                    KeyboardButton(text=_("🏠 Host")),
                    KeyboardButton(text=_("🚫 Can't Host")),
                ],
                [
                    KeyboardButton(text=_("🏨 Airbnb")),
                    KeyboardButton(text=_("👁️ See All")),
                ],
            ],
        )
        return kb

    @staticmethod
    def role_filter() -> ReplyKeyboardMarkup:
        """Filter profiles by role preference - Who do you want to see?"""
        kb = ReplyKeyboardMarkup(
            resize_keyboard=True,
            keyboard=[
                [
                    KeyboardButton(text=_("🔝 Tops")),
                    KeyboardButton(text=_("🔽 Bottoms")),
                ],
                [
                    KeyboardButton(text=_("🔄 Verse")),
                    KeyboardButton(text=_("👁️ Everyone")),
                ],
            ],
        )
        return kb

    @staticmethod
    def city(user: UserModel | None):
        builder = ReplyKeyboardBuilder()
        if user.profile and user.profile.city != "📍":
            builder.button(text=_("Keep previous"))
        builder.button(
            text=_("📍 Send location"),
            request_location=True,
        )
        builder.adjust(1)
        return builder.as_markup(resize_keyboard=True)

    @staticmethod
    def leave_previous(profile: ProfileModel) -> ReplyKeyboardMarkup:
        if profile:
            kb = ReplyKeyboardMarkup(
                resize_keyboard=True,
                one_time_keyboard=True,
                keyboard=[
                    [KeyboardButton(text=_("Keep previous"))],
                ],
            )
        else:
            kb = del_kb
        return kb