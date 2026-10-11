from aiogram import F, types
from aiogram.filters import Command
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.filters.kb_filter import StatsCallback
from app.keyboards.inline.admin import stats_ikb
from app.routers import admin_router, common_router
from data.config import GRAPH_FILE_PATH
from database.services.stats import Stats
from utils.graphs import StatsGraph
from .access import is_admin_id

stats_graph = StatsGraph()


USER_STATS = """
👤 Users: {}\t| 🚫 Blocked: {}
✉️ Referrals: {}

🌍 Most popular language: {}
"""


PROFILE_STATS = """
📂 Profile: {} | 🔕 Inactive: {}
🙍‍♂ Guys: {} | 🙍‍♀ Girls: {}

💘 Matches: {}

🕘 Age: {}
🏙 City: {}
"""


REFERRAL_STATS = """
📊 Total Referrals: {}

📈 Sources breakdown:
{}
"""


@common_router.message(Command("stats"))
@admin_router.message(StateFilter(None), F.text == "📊 Statistics")
async def _stats_command(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    """Отправляет администратору меню статистики"""
    if not is_admin_id(message.from_user.id):
        return

    await state.clear()
    await message.answer("Stats sending...")

    data = await Stats.get_registration_data(session)
    stats_graph.create_user_registration_graph(data)
    users_stats = await Stats.user_stats(session)

    text = USER_STATS.format(
        users_stats["count"],
        users_stats["banned_count"],
        users_stats["total_referrals"],
        users_stats["most_popular_language"],
    )

    photo = types.FSInputFile(GRAPH_FILE_PATH)
    await message.answer_photo(photo=photo, caption=text, reply_markup=stats_ikb("User"))


@admin_router.callback_query(StateFilter(None), StatsCallback.filter())
async def _stats_callback(
    callback: types.CallbackQuery, callback_data: StatsCallback, session: AsyncSession
) -> None:
    """Отправляет администратору график и статистику"""
    if callback_data.type == "User":
        data = await Stats.get_registration_data(session)
        stats_graph.create_user_registration_graph(data)
        users_stats = await Stats.user_stats(session)

        text = USER_STATS.format(
            users_stats["count"],
            users_stats["banned_count"],
            users_stats["total_referrals"],
            users_stats["most_popular_language"],
        )

    elif callback_data.type == "Profile":
        gender_data = await Stats.get_gender_data(session)

        stats_graph.create_gender_pie_chart(gender_data)
        match_stats = await Stats.match_stats(session)
        profile_stats = await Stats.profile_stats(session)
        text = PROFILE_STATS.format(
            profile_stats["count"],
            profile_stats["inactive_profile"],
            profile_stats["male_count"],
            profile_stats["female_count"],
            match_stats[0],
            profile_stats["average_age"],
            profile_stats["most_popular_city"],
        )

    elif callback_data.type == "Referral":
        referral_stats = await Stats.referral_stats(session)
        stats_graph.create_referral_sources_chart(referral_stats["sources"])

        # Форматируем список источников
        sources_text = ""
        for source, count in referral_stats["sources"].items():
            percentage = (
                (count / referral_stats["total_referrals"] * 100)
                if referral_stats["total_referrals"] > 0
                else 0
            )
            sources_text += f"• {source}: {count} ({percentage:.1f}%)\n"

        if not sources_text:
            sources_text = "No referral data available"

        text = REFERRAL_STATS.format(referral_stats["total_referrals"], sources_text)

    media = types.InputMediaPhoto(media=types.FSInputFile(GRAPH_FILE_PATH), caption=text)
    await callback.message.edit_media(media=media, reply_markup=stats_ikb(callback_data.type))
