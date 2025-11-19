"""
Age filter handler for setting age preferences when browsing profiles.
"""

from aiogram import F, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.default.base import age_filter_kb, mode_menu_kb
from app.routers import dating_router
from app.states.default import AgeFilter
from app.text import message_text as mt
from database.models import UserModel


@dating_router.message(F.text == "🎂")
async def age_filter_start(
    message: types.Message,
    state: FSMContext,
    user: UserModel,
    session: AsyncSession
) -> None:
    """Start age filter setup - ask for minimum age"""
    await state.set_state(AgeFilter.min_age)
    
    # Get current age filter if exists
    data = await state.get_data()
    min_age = data.get("min_age", 18)
    max_age = data.get("max_age", 99)
    
    await message.answer(
        mt.AGE_FILTER_START(min_age=min_age, max_age=max_age),
        reply_markup=age_filter_kb
    )


@dating_router.message(AgeFilter.min_age, F.text.regexp(r"^\d+$"))
async def age_filter_min_set(
    message: types.Message,
    state: FSMContext,
    user: UserModel,
    session: AsyncSession
) -> None:
    """Set minimum age and ask for maximum"""
    min_age = int(message.text)
    
    # Validate minimum age
    if min_age < 18:
        await message.answer(mt.AGE_FILTER_TOO_LOW)
        return
    
    if min_age > 99:
        await message.answer(mt.AGE_FILTER_TOO_HIGH)
        return
    
    # Save min age and move to max age
    await state.update_data(min_age=min_age)
    await state.set_state(AgeFilter.max_age)
    
    await message.answer(
        mt.AGE_FILTER_MAX(min_age=min_age),
        reply_markup=age_filter_kb
    )


@dating_router.message(AgeFilter.max_age, F.text.regexp(r"^\d+$"))
async def age_filter_max_set(
    message: types.Message,
    state: FSMContext,
    user: UserModel,
    session: AsyncSession
) -> None:
    """Set maximum age and confirm"""
    max_age = int(message.text)
    data = await state.get_data()
    min_age = data.get("min_age", 18)
    
    # Validate maximum age
    if max_age < 18:
        await message.answer(mt.AGE_FILTER_TOO_LOW)
        return
    
    if max_age > 99:
        await message.answer(mt.AGE_FILTER_TOO_HIGH)
        return
    
    if max_age < min_age:
        await message.answer(mt.AGE_FILTER_INVALID_RANGE(min_age=min_age))
        return
    
    # Save max age
    await state.update_data(max_age=max_age)
    
    # Get current mode and hosting filter to preserve them
    current_mode = data.get("current_mode")
    hosting_filter = data.get("hosting_filter", "all")
    
    # Clear state and restore all data
    await state.clear()
    await state.update_data(
        min_age=min_age,
        max_age=max_age,
        current_mode=current_mode,
        hosting_filter=hosting_filter
    )
    
    await message.answer(
        mt.AGE_FILTER_SET(min_age=min_age, max_age=max_age),
        reply_markup=mode_menu_kb
    )


@dating_router.message(AgeFilter.min_age, F.text == "↩️")
@dating_router.message(AgeFilter.max_age, F.text == "↩️")
async def age_filter_cancel(
    message: types.Message,
    state: FSMContext,
    user: UserModel,
    session: AsyncSession
) -> None:
    """Cancel age filter setup"""
    data = await state.get_data()
    current_mode = data.get("current_mode")
    min_age = data.get("min_age")
    max_age = data.get("max_age")
    hosting_filter = data.get("hosting_filter", "all")
    
    # Restore state without the filter states
    await state.clear()
    await state.update_data(
        current_mode=current_mode,
        min_age=min_age,
        max_age=max_age,
        hosting_filter=hosting_filter
    )
    
    await message.answer(
        mt.AGE_FILTER_CANCELLED,
        reply_markup=mode_menu_kb
    )


@dating_router.message(AgeFilter.min_age)
@dating_router.message(AgeFilter.max_age)
async def age_filter_invalid(
    message: types.Message,
    state: FSMContext
) -> None:
    """Handle invalid age input"""
    await message.answer(mt.AGE_FILTER_INVALID_INPUT)