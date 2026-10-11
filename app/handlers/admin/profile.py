from aiogram import types
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.business.profile_service import send_profile
from app.routers import common_router
from database.services.profile import Profile
from .access import is_admin_id


@common_router.message(Command("profile"))
async def _admin_command(
    message: types.Message, command: CommandObject, session: AsyncSession, state: FSMContext
) -> None:
    """Админ панель"""
    if not is_admin_id(message.from_user.id):
        return

    await state.clear()
    try:
        profile_id = command.args.lower()
        profile = await Profile.get(session=session, id=int(profile_id))
        await send_profile(message.chat.id, profile, session)
    except:
        await message.answer("Profile not found")
