from aiogram import types
from aiogram.filters.state import StateFilter

from app.routers import dating_router
from app.states.default import ProfileCreate, ProfileEdit
from app.text import message_text as mt


@dating_router.message(StateFilter(ProfileCreate.role))
async def _incorrect_role(message: types.Message):
    """Role filter error"""
    await message.answer(mt.INVALID_RESPONSE)


@dating_router.message(StateFilter(ProfileCreate.find_role))
async def _incorrect_find_role(message: types.Message):
    """Find role filter error"""
    await message.answer(mt.INVALID_RESPONSE)


@dating_router.message(StateFilter(ProfileCreate.photo, ProfileEdit.photo))
async def _incorrect_photo(message: types.Message):
    """Photo filter error"""
    await message.answer(mt.INVALID_PHOTO)


@dating_router.message(StateFilter(ProfileCreate.name))
async def _incorrect_name(message: types.Message):
    """Name filter error"""
    await message.answer(mt.INVALID_LONG_RESPONSE)


@dating_router.message(StateFilter(ProfileCreate.age))
async def _incorrect_age(message: types.Message):
    """Age filter error"""
    await message.answer(mt.INVALID_AGE)


@dating_router.message(StateFilter(ProfileCreate.city))
async def _incorrect_city(message: types.Message):
    """City filter error"""
    await message.answer(mt.INVALID_CITY_RESPONSE)


@dating_router.message(StateFilter(ProfileCreate.description, ProfileEdit.description))
async def _incorrect_description(message: types.Message):
    """Description filter error"""
    await message.answer(mt.INVALID_LONG_RESPONSE)