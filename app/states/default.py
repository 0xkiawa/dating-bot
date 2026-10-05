from aiogram.fsm.state import State, StatesGroup


class LikeResponse(StatesGroup):
    response = State()


class ProfileCreate(StatesGroup):
    name = State()
    role = State()
    # REMOVED: find_role = State()  # No longer needed
    age = State()
    city = State()
    photo = State()
    photo_privacy = State()  # NEW: optional blur/reveal setting for uploaded photos
    description = State()
    hosting = State()


class ProfileEdit(StatesGroup):
    photo = State()
    description = State()


class Search(StatesGroup):
    search = State()
    message = State()
    hosting_filter = State()
    role_filter = State()
    age_filter_min = State()  # NEW: age step in the browse flow
    age_filter_max = State()  # NEW: age step in the browse flow


# Standalone age filter states (used by the separate /age_filter command flow — unrelated to Search)
class AgeFilter(StatesGroup):
    min_age = State()
    max_age = State()

class PhotoPrivacyEdit(StatesGroup):
    selecting = State()