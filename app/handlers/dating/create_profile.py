from aiogram import F, types
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

import app.filters.create_profile_filtres as filters
from app.business.menu_service import menu
from app.keyboards.default.registration_form import RegistrationFormKb
from app.routers import dating_router
from app.states.default import ProfileCreate
from app.text import message_text as mt
from database.models.user import UserModel
from database.services import Profile
from database.services.profile_media import ProfileMedia
from database.services.user import User

from .profile import profile_command


@dating_router.message(StateFilter(None), F.text == "🔄")
@dating_router.message(StateFilter(None), filters.IsCreate())
async def _create_profile_command(message: types.Message, state: FSMContext, user: UserModel):
    """Starts user profile creation process.
    Also used for recreating profile"""
    await state.set_state(ProfileCreate.name)

    kb = RegistrationFormKb.name(user)
    await message.answer(text=mt.NAME, reply_markup=kb)


# -< Name >-
@dating_router.message(StateFilter(ProfileCreate.name), F.text, filters.IsName())
async def _name(message: types.Message, state: FSMContext):
    await state.set_state(ProfileCreate.role)
    await state.update_data(name=message.text)

    kb = RegistrationFormKb.role()
    await message.answer(text=mt.ROLE, reply_markup=kb)


# -< Role >-
@dating_router.message(StateFilter(ProfileCreate.role), F.text, filters.IsRole())
async def _role(message: types.Message, state: FSMContext, role: str):
    await state.set_state(ProfileCreate.find_role)
    await state.update_data(role=role)

    kb = RegistrationFormKb.find_role()
    await message.answer(text=mt.FIND_ROLE, reply_markup=kb)


# -< Find role >-
@dating_router.message(StateFilter(ProfileCreate.find_role), F.text, filters.IsFindRole())
async def _find_role(
    message: types.Message, state: FSMContext, find_role: str, user: UserModel
):
    await state.set_state(ProfileCreate.city)
    await state.update_data(find_role=find_role)

    kb = RegistrationFormKb.city(user)
    await message.answer(text=mt.CITY, reply_markup=kb)


# -< City >-
@dating_router.message(StateFilter(ProfileCreate.city), F.text | F.location, filters.IsCity())
async def _city(
    message: types.Message,
    state: FSMContext,
    latitude: str,
    longitude: str,
    city: str,
    is_shared_location: bool,
    user: UserModel,
):
    if not (latitude or longitude):
        if user.profile:
            city = user.profile.city
            latitude = user.profile.latitude
            longitude = user.profile.longitude
            is_shared_location = user.profile.is_shared_location
        else:
            return

    await state.set_state(ProfileCreate.age)
    await state.update_data(
        city=city,
        latitude=latitude,
        longitude=longitude,
        is_shared_location=is_shared_location,
    )

    kb = RegistrationFormKb.age(user)
    await message.answer(text=mt.AGE, reply_markup=kb)


# -< Age >-
@dating_router.message(StateFilter(ProfileCreate.age), F.text, filters.IsAge())
async def _age(message: types.Message, state: FSMContext, user: UserModel):
    await state.set_state(ProfileCreate.photo)
    await state.update_data(age=message.text)

    await state.update_data(photos=[])
    kb = RegistrationFormKb.photo(user)
    await message.answer(text=mt.PHOTO, reply_markup=kb)


# -< Photo >-
@dating_router.message(StateFilter(ProfileCreate.photo), filters.IsPhoto())
async def _photo(message: types.Message, state: FSMContext, user: UserModel, session: AsyncSession):
    data = await state.get_data()
    photos = data.get("photos", [])

    if message.text in filters.LEAVE_PREVIOUS_OPTIONS:
        # Get existing photos from user profile
        existing_photos = await ProfileMedia.get_profile_photos(session, user.id)
        if existing_photos:
            photos = [photo.media for photo in existing_photos]
            await state.update_data(photos=photos)

        # Move to description
        kb = RegistrationFormKb.description(user)
        await message.answer(text=mt.DESCRIPTION, reply_markup=kb)
        await state.set_state(ProfileCreate.description)
        return

    elif message.text in filters.SAVE_PHOTO_OPTIONS:
        if not photos:
            await message.answer(mt.PHOTO_NO_UPLOADED)
            return

        # Update state data with current photos
        await state.update_data(photos=photos)

        # Move to description
        kb = RegistrationFormKb.description(user)
        await message.answer(text=mt.DESCRIPTION, reply_markup=kb)
        await state.set_state(ProfileCreate.description)
        return

    elif message.photo:
        # Check photo limit
        if len(photos) >= 3:
            await message.answer(mt.PHOTO_LIMIT_REACHED)
            return

        new_photo = message.photo[-1].file_id
        photos.append(new_photo)
        await state.update_data(photos=photos)

        new_count = len(photos)

        if new_count < 3:
            await message.answer(
                text=mt.PHOTO_PROGRESS(current=new_count),
                reply_markup=RegistrationFormKb.photo_add(),
            )
        else:
            # All 3 photos uploaded - move to description
            await message.answer(mt.PHOTO_ALL_UPLOADED())

            kb = RegistrationFormKb.description(user)
            await message.answer(text=mt.DESCRIPTION, reply_markup=kb)
            await state.set_state(ProfileCreate.description)
    else:
        await message.answer(mt.PHOTO_UPLOAD_INSTRUCTION)


# -< Description >-
@dating_router.message(StateFilter(ProfileCreate.description), F.text, filters.IsDescription())
async def _description(
    message: types.Message, state: FSMContext, user: UserModel, session: AsyncSession
):
    data = await state.get_data()
    
    if message.text in filters.SKIP_OPTIONS:
        description = ""
    elif message.text in filters.LEAVE_PREVIOUS_OPTIONS and user.profile:
        description = user.profile.description
    else:
        description = message.text

    await state.update_data(description=description)
    
    # NEW: Move to hosting question
    await state.set_state(ProfileCreate.hosting)
    kb = RegistrationFormKb.hosting()
    await message.answer(text=mt.HOSTING, reply_markup=kb)


# -< Hosting >- NEW
@dating_router.message(StateFilter(ProfileCreate.hosting), F.text)
async def _hosting(
    message: types.Message, state: FSMContext, user: UserModel, session: AsyncSession
):
    # Map button text to hosting values
    hosting_map = {
        "✅ Yes": "yes",
        "❌ No": "no",
        "🏨 Airbnb": "airbnb"
    }
    
    hosting = hosting_map.get(message.text)
    if not hosting:
        await message.answer("Please select a valid option.")
        return
    
    data = await state.get_data()
    photos = data.get("photos", [])
    
    await state.clear()

    await Profile.create_or_update(
        session=session,
        id=message.from_user.id,
        role=data["role"],
        find_role=data["find_role"],
        photos=photos,
        name=data["name"],
        age=int(data["age"]),
        city=data["city"],
        latitude=float(data["latitude"]),
        longitude=float(data["longitude"]),
        is_shared_location=bool(data["is_shared_location"]),
        description=data.get("description", ""),
        hosting=hosting,  # NEW
    )

    await message.answer(mt.PROFILE_CREATED)
    await menu(chat_id=user.id)


# -< Flow >-
# 1. -< Name >-
# 2. -< Role >-
# 3. -< Find role >-
# 4. -< City >-
# 5. -< Age >-
# 6. -< Photo >-
# 7. -< Description >-
# 8. -< Hosting >- NEW