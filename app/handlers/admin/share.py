from aiogram import types
from aiogram.filters import Command, CommandObject
from aiogram.filters.state import StateFilter
from sqlalchemy.ext.asyncio import AsyncSession

from app.handlers.admin.access import is_admin_id
from app.routers import common_router
from database.services.share import disable_share_link


@common_router.message(StateFilter("*"), Command("shareoff"))
async def disable_user_share_link(
    message: types.Message, command: CommandObject, session: AsyncSession
) -> None:
    """Allow an administrator to disable a member's share link by Telegram ID."""
    if not is_admin_id(message.from_user.id):
        return
    try:
        target_id = int(command.args or "")
    except ValueError:
        await message.answer("Usage: /shareoff <user_id>")
        return

    if await disable_share_link(session, target_id):
        await message.answer(f"Share link for user <code>{target_id}</code> disabled.")
    else:
        await message.answer(f"User <code>{target_id}</code> has no share link.")
