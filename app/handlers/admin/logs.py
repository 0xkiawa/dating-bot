from aiogram import F, types
from aiogram.filters import Command
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile

from app.routers import admin_router, common_router
from data.config import LOG_FILE_PATH
from .access import is_admin_id


@common_router.message(Command("log"))
@common_router.message(Command("logs"))
@admin_router.message(StateFilter(None), F.text == "📝 Logs")
async def _logs_command(message: types.Message, state: FSMContext) -> None:
    """Отправляет администратору последний файл логов бота"""
    if not is_admin_id(message.from_user.id):
        return

    await state.clear()
    await message.answer("Logs sending...")
    await message.answer_document(document=FSInputFile(LOG_FILE_PATH))
