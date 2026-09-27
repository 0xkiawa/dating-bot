
from aiogram.filters import Filter
from aiogram.types import Message

from loader import _
from utils.geopy import get_city_name, get_coordinates

ROLE_MAP = {
    "Top": "top",
    "Bottom": "bottom",
    "Verse": "verse",
}

FIND_ROLE_MAP = {
    "Tops": "top",
    "Bottoms": "bottom",
    "Verse": "verse",
    "Everyone": "all",
}

LEAVE_PREVIOUS_OPTIONS = (
    "Keep previous",
    "Leave previous",
)

SKIP_OPTIONS = (
    "Skip",
)

START_COMMAND_OPTIONS = (
    "/create",
    "Create a profile",
)

SAVE_PHOTO_OPTIONS = (
    "That's all, save photos",
    "That's it, keep the photo",
)


def localized_options(options: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(_(option) for option in options)


class IsCreate(Filter):
    async def __call__(self, message: Message) -> bool:
        return bool(message.text == "/create" or message.text == _("Create a profile"))


class IsRole(Filter):
    async def __call__(self, message: Message) -> dict | bool:
        role_map = {_(label): value for label, value in ROLE_MAP.items()}
        if message.text in role_map:
            return {"role": role_map[message.text]}
        return False


class IsFindRole(Filter):
    async def __call__(self, message: Message) -> dict | bool:
        role_map = {_(label): value for label, value in FIND_ROLE_MAP.items()}
        if message.text in role_map:
            return {"find_role": role_map[message.text]}
        return False


class IsPhoto(Filter):
    async def __call__(self, message: Message) -> bool:
        return bool(
            message.photo
            or message.text in localized_options(LEAVE_PREVIOUS_OPTIONS)
            or message.text in localized_options(SAVE_PHOTO_OPTIONS)
        )


class IsName(Filter):
    async def __call__(self, message: Message) -> bool:
        return bool(len(message.text) < 70)


class IsAge(Filter):
    async def __call__(self, message: Message) -> bool:
        return bool(message.text.isdigit() and int(message.text) < 100 and int(message.text) > 6)


class IsCity(Filter):
    async def __call__(self, message: Message) -> bool:
        latitude: float = None
        longitude: float = None
        city: str = None
        is_shared_location: bool = None

        if message.location:
            latitude = message.location.latitude
            longitude = message.location.longitude
            city = get_city_name(latitude=latitude, longitude=longitude)
            is_shared_location = True
        if message.text:
            if message.text.isdigit() and len(message.text) <= 1:
                return False
            if message.text in localized_options(LEAVE_PREVIOUS_OPTIONS):
                pass
            elif coordinates := get_coordinates(message.text):
                latitude = coordinates[0]
                longitude = coordinates[1]
                city = message.text
                is_shared_location = False
            else:
                return False

        return {
            "latitude": latitude,
            "longitude": longitude,
            "city": city,
            "is_shared_location": is_shared_location,
        }


class IsDescription(Filter):
    async def __call__(self, message: Message) -> bool:
        return bool(
            len(message.text) < 900 or message.text in localized_options(SKIP_OPTIONS),
        )


class IsMessageToUser(Filter):
    async def __call__(self, message: Message) -> bool:
        return bool(len(message.text) < 250)
