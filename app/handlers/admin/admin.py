from aiogram import types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from app.commands import set_admins_commands
from app.keyboards.default.base import admin_kb
from app.routers import common_router
from .access import is_admin_id


@common_router.message(Command("admin"))
async def _admin_command(message: types.Message, state: FSMContext) -> None:
    """Админ панель"""
    if not is_admin_id(message.from_user.id):
        return

    await state.clear()
    await set_admins_commands(message.from_user.id)
    text = """
🔧 <b>Admin panel</b>

/admin - Admin panel
/ban - Block user
/unban - Unblock user
/stats - Send stats
/logs - Send logs
/mailing - Mailing to all users
/profile - Check user profile
"""
    await message.answer(
        text=text,
        reply_markup=admin_kb,
        parse_mode="HTML",
    )
