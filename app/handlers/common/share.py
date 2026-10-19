from urllib.parse import urlencode

from aiogram import F, types
from aiogram.filters import Command
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.deep_linking import create_start_link
from sqlalchemy.ext.asyncio import AsyncSession

from app.filters.kb_filter import MainMenuCallback, ShareLinkCallback
from app.routers import common_router
from app.states.default import Search
from database.models import UserModel
from database.models.share import ShareLinkModel
from database.services.share import (
    ShareRerollLimitError,
    consume_pending_shared_view,
    disable_share_link,
    get_pending_shared_target,
    issue_or_reroll_share_link,
)
from loader import bot
from app.business.profile_service import send_shared_discovery_profile


CONFIRM_SHARE_TEXT = (
    "Anyone who has your link can open CONQUEER. Members who already use the bot can "
    "see your normal profile card. New visitors must accept the Terms and create a "
    "profile before they can see you. Your link contains no personal details, and "
    "you can switch it off any time.\n\nCreate your share link?"
)
SHARE_MESSAGE = "Meet people on CONQUEER. Open the bot to get started."


def _share_keyboard(link: str | None, active: bool) -> InlineKeyboardMarkup:
    rows = []
    if active and link:
        share_url = "https://t.me/share/url?" + urlencode(
            {"url": link, "text": SHARE_MESSAGE}
        )
        rows.append([InlineKeyboardButton(text="Share", url=share_url)])
    rows.append(
        [
            InlineKeyboardButton(
                text="New link" if link else "Create link",
                callback_data=ShareLinkCallback(action="reroll").pack(),
            )
        ]
    )
    if active:
        rows.append(
            [
                InlineKeyboardButton(
                    text="Turn off link",
                    callback_data=ShareLinkCallback(action="disable").pack(),
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _show_share_setup(
    event: types.Message | types.CallbackQuery,
    user: UserModel,
    session: AsyncSession,
    *,
    edit: bool = False,
) -> None:
    if not user.profile or not user.profile.is_active:
        text = "Create and activate your profile before sharing it."
        if edit and isinstance(event, types.CallbackQuery):
            await event.message.edit_text(text)
        else:
            await event.answer(text)
        return

    link_row = await session.get(ShareLinkModel, user.id)
    if not link_row:
        if edit and isinstance(event, types.CallbackQuery):
            await event.message.edit_text(
                CONFIRM_SHARE_TEXT,
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="Create my link",
                                callback_data=ShareLinkCallback(action="confirm").pack(),
                            )
                        ]
                    ]
                ),
            )
        else:
            await event.answer(
                CONFIRM_SHARE_TEXT,
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="Create my link",
                                callback_data=ShareLinkCallback(action="confirm").pack(),
                            )
                        ]
                    ]
                ),
            )
        return

    if link_row.is_enabled:
        url = await create_start_link(bot, link_row.slug)
        text = (
            f"Your CONQUEER profile link:\n{url}\n\n"
            "New visitors must accept the Terms. Members who already accepted them can "
            "open your profile card directly."
        )
    else:
        url = None
        text = "Your profile link is off. Create a new link whenever you want to share again."
    markup = _share_keyboard(url, bool(link_row.is_enabled))
    if edit and isinstance(event, types.CallbackQuery):
        await event.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
    else:
        await event.answer(text, reply_markup=markup, disable_web_page_preview=True)


@common_router.message(StateFilter("*"), Command("share"))
@common_router.message(StateFilter("*"), F.text == "🔗 Share my profile")
async def share_profile_command(
    message: types.Message, user: UserModel, session: AsyncSession
) -> None:
    await _show_share_setup(message, user, session)


@common_router.callback_query(MainMenuCallback.filter(F.action == "share"))
async def share_profile_from_menu(
    callback: types.CallbackQuery, user: UserModel, session: AsyncSession
) -> None:
    await callback.answer()
    await _show_share_setup(callback, user, session, edit=True)


@common_router.callback_query(ShareLinkCallback.filter(F.action == "confirm"))
async def confirm_share_link(
    callback: types.CallbackQuery,
    user: UserModel,
    session: AsyncSession,
) -> None:
    await callback.answer()
    try:
        await issue_or_reroll_share_link(session, user.id)
    except ValueError:
        await callback.message.edit_text("Create and activate your profile before sharing it.")
        return
    await _show_share_setup(callback, user, session, edit=True)


@common_router.callback_query(ShareLinkCallback.filter(F.action == "reroll"))
async def reroll_share_link(
    callback: types.CallbackQuery,
    user: UserModel,
    session: AsyncSession,
) -> None:
    await callback.answer()
    try:
        await issue_or_reroll_share_link(session, user.id, reroll=True)
    except ShareRerollLimitError:
        await callback.message.answer(
            "You can create up to 3 new links in 24 hours. Try again later."
        )
    except ValueError:
        await callback.message.edit_text("Create and activate your profile before sharing it.")
        return
    await _show_share_setup(callback, user, session, edit=True)


@common_router.callback_query(ShareLinkCallback.filter(F.action == "disable"))
async def turn_off_share_link(
    callback: types.CallbackQuery,
    user: UserModel,
    session: AsyncSession,
) -> None:
    await callback.answer()
    await disable_share_link(session, user.id)
    await _show_share_setup(callback, user, session, edit=True)


async def deliver_pending_share_to_existing_member(
    *, user: UserModel, state: FSMContext, session: AsyncSession
) -> bool:
    pending_target = await get_pending_shared_target(session, user.id)
    if not pending_target or not user.profile:
        return False

    pending, target = pending_target
    viewer_mode = user.current_mode or target.current_mode
    await state.clear()
    await state.set_state(Search.search)
    await state.update_data(
        ids=[target.id],
        current_mode=viewer_mode,
        shared_card_id=target.id,
        shared_card_mode=target.current_mode,
        shared_pending_id=pending.id,
        filter_screen="search",
    )
    try:
        sent = await send_shared_discovery_profile(
            user=user,
            target_id=target.id,
            pending_id=pending.id,
            session=session,
        )
    except Exception:
        await state.clear()
        raise
    if not sent:
        await state.clear()
        return False
    await consume_pending_shared_view(session, pending.id)
    await state.update_data(
        active_card_chat_id=sent.chat.id,
        active_card_message_id=sent.message_id,
    )
    return True
