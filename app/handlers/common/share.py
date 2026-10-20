from urllib.parse import urlencode

from aiogram import F, types
from aiogram.filters import Command
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent,
)
from aiogram.utils.deep_linking import create_start_link
from sqlalchemy.ext.asyncio import AsyncSession

from app.filters.kb_filter import MainMenuCallback, ShareLinkCallback
from app.consent import has_current_consent
from app.routers import common_router
from app.states.default import Search, ShareMessageEdit
from database.models import UserModel
from database.models.share import ShareLinkModel
from database.services.user import User
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
SHARE_MODES = {
    "fun": ("FUN NOW", "🍆👅🍑💦"),
    "dates": ("DATES NOW", "❤️🥂"),
    "friends": ("FRIENDS NOW", "🤝"),
}


def _share_mode_copy(user: UserModel) -> tuple[str, str]:
    return SHARE_MODES.get(user.current_mode, ("PROFILE NOW", "🌈"))


def _default_share_message(user: UserModel) -> str:
    profile = user.profile
    if not profile:
        return "Meet people on CONQUEER. Open the bot to get started."

    roles = {"top": "Top", "bottom": "Bottom", "verse": "Verse"}
    looking_for = {
        "top": "a Top",
        "bottom": "a Bottom",
        "verse": "a Verse",
        "all": "any role",
    }
    mode_text, mode_emojis = _share_mode_copy(user)
    role_text = roles.get(profile.role, "CONQUEER member")
    looking_for_text = looking_for.get(profile.find_role, "any role")
    article = "a " if role_text in {"Top", "Bottom", "Verse"} else ""
    return (
        f"Hey :) I'm {article}{role_text}, looking for {mode_text} with "
        f"{looking_for_text}. Check my profile out! {mode_emojis}"
    )


def _share_message(user: UserModel, link_row: ShareLinkModel) -> str:
    return link_row.share_message or _default_share_message(user)


def _share_card_keyboard(link: str, user: UserModel) -> InlineKeyboardMarkup:
    mode_text, mode_emojis = _share_mode_copy(user)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{mode_text} {mode_emojis}", url=link)]
        ]
    )


def _share_management_keyboard(
    *,
    active: bool,
    telegram_share_url: str | None = None,
    inline_query: str | None = None,
    has_custom_message: bool = False,
) -> InlineKeyboardMarkup:
    rows = []
    if active and inline_query:
        rows.append(
            [InlineKeyboardButton(text="📤 Share profile", switch_inline_query=inline_query)]
        )
    elif active and telegram_share_url:
        rows.append(
            [InlineKeyboardButton(text="📤 Share profile", url=telegram_share_url)]
        )
    if active:
        rows.append(
            [
                InlineKeyboardButton(
                    text="Edit share message",
                    callback_data=ShareLinkCallback(action="edit_message").pack(),
                )
            ]
        )
        if has_custom_message:
            rows.append(
                [
                    InlineKeyboardButton(
                        text="Reset message to default",
                        callback_data=ShareLinkCallback(action="reset_message").pack(),
                    )
                ]
            )
    rows.append(
        [
            InlineKeyboardButton(
                text="New link" if active else "Create link",
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
        inline_enabled = bool((await bot.get_me()).supports_inline_queries)
        if inline_enabled:
            inline_query = link_row.slug
            telegram_share_url = None
            text = (
                "Tap 📤 Share profile, choose a chat, then select the share result. "
                "The recipient gets your caption and a clickable mode button. The "
                "caption and button are not posted in this bot chat."
            )
        else:
            inline_query = None
            url = await create_start_link(bot, link_row.slug)
            telegram_share_url = "https://t.me/share/url?" + urlencode(
                {"url": url, "text": _share_message(user, link_row)}
            )
            text = (
                "Tap 📤 Share profile to send your caption and profile link. To send "
                "a short clickable mode button with the caption, inline mode must "
                "be enabled for this bot in @BotFather."
            )
    else:
        inline_query = None
        telegram_share_url = None
        text = "Your profile link is off. Create a new link whenever you want to share again."
    active = bool(link_row.is_enabled)
    markup = _share_management_keyboard(
        active=active,
        telegram_share_url=telegram_share_url,
        inline_query=inline_query,
        has_custom_message=bool(link_row.share_message),
    )
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


@common_router.inline_query()
async def share_profile_inline_query(
    inline_query: types.InlineQuery, session: AsyncSession
) -> None:
    """Send the caption and compact profile button directly into the chosen chat."""
    link_row = await session.get(ShareLinkModel, inline_query.from_user.id)
    owner = await User.get_with_profile(session, inline_query.from_user.id)
    if (
        not link_row
        or not link_row.is_enabled
        or link_row.slug != inline_query.query.strip()
        or not owner
        or not has_current_consent(owner)
        or owner.status == 0
        or not owner.profile
        or not owner.profile.is_active
        or owner.profile.age < 18
        or owner.current_mode not in SHARE_MODES
    ):
        await inline_query.answer([], cache_time=0, is_personal=True)
        return

    profile_url = await create_start_link(bot, link_row.slug)
    result = InlineQueryResultArticle(
        id=link_row.slug,
        title="Share my CONQUEER profile",
        description="Send your saved caption with a clickable mode button.",
        input_message_content=InputTextMessageContent(
            message_text=_share_message(owner, link_row),
            parse_mode=None,
        ),
        reply_markup=_share_card_keyboard(profile_url, owner),
    )
    await inline_query.answer([result], cache_time=0, is_personal=True)


@common_router.callback_query(ShareLinkCallback.filter(F.action == "edit_message"))
async def start_share_message_edit(
    callback: types.CallbackQuery,
    user: UserModel,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    await callback.answer()
    link_row = await session.get(ShareLinkModel, user.id)
    if not link_row or not link_row.is_enabled:
        await _show_share_setup(callback, user, session, edit=True)
        return
    await state.set_state(ShareMessageEdit.message)
    await callback.message.edit_text(
        "Send the custom caption you want recipients to see (up to 1000 characters). "
        "Your current default or custom caption stays hidden here. Use /cancel to stop editing.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Cancel",
                        callback_data=ShareLinkCallback(action="cancel_message_edit").pack(),
                    )
                ]
            ]
        ),
    )


@common_router.callback_query(
    ShareLinkCallback.filter(F.action == "cancel_message_edit")
)
async def cancel_share_message_edit(
    callback: types.CallbackQuery,
    user: UserModel,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    await callback.answer()
    await state.clear()
    await _show_share_setup(callback, user, session, edit=True)


@common_router.callback_query(ShareLinkCallback.filter(F.action == "reset_message"))
async def reset_share_message(
    callback: types.CallbackQuery,
    user: UserModel,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    await callback.answer()
    link_row = await session.get(ShareLinkModel, user.id)
    if link_row:
        link_row.share_message = None
        await session.commit()
    await state.clear()
    await _show_share_setup(callback, user, session, edit=True)


@common_router.message(
    StateFilter(ShareMessageEdit.message), F.text & ~F.text.startswith("/")
)
async def save_custom_share_message(
    message: types.Message,
    user: UserModel,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    custom_message = (message.text or "").strip()
    if not custom_message:
        await message.answer("Send a message with at least one character.")
        return
    if len(custom_message) > 1000:
        await message.answer("Keep your share message to 1000 characters or fewer.")
        return

    link_row = await session.get(ShareLinkModel, user.id)
    if not link_row or not link_row.is_enabled:
        await state.clear()
        await message.answer("Your share link is off. Create a new link before editing its message.")
        return
    link_row.share_message = custom_message
    await session.commit()
    await state.clear()
    await message.answer("Your custom share message is saved and will be sent to recipients.")
    await _show_share_setup(message, user, session)


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
