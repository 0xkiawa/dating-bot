import os
import sys

from aiogram import types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from app.routers import common_router
from .access import is_admin_id


@common_router.message(Command("restart"))
async def _restart_command(message: types.Message, state: FSMContext) -> None:
    if not is_admin_id(message.from_user.id):
        return

    await state.clear()
    await message.answer("Restarting and updating the bot...")
    os.system("git pull")
    os.execv(sys.executable, ["uv", "main.py"])
