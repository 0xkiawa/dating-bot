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


# Age filter states
class AgeFilter(StatesGroup):
    min_age = State()
    max_age = State()