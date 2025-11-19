from aiogram.fsm.state import State, StatesGroup


class LikeResponse(StatesGroup):
    response = State()


class ProfileCreate(StatesGroup):
    name = State()
    role = State()  # Changed from gender
    find_role = State()  # Changed from find_gender
    age = State()
    city = State()
    photo = State()
    description = State()
    hosting = State()  # NEW: Can you host?


class ProfileEdit(StatesGroup):
    photo = State()
    description = State()


class Search(StatesGroup):
    search = State()
    message = State()
    hosting_filter = State()  # NEW: Filter by hosting preference


# NEW: Age filter states
class AgeFilter(StatesGroup):
    min_age = State()
    max_age = State()