import re
from datetime import date
from pathlib import Path

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, Update
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.models.user import UserModel, UserStatus
from loader import bot

# Bump this value whenever either policy changes. Users who accepted an older
# version will be asked to review and accept the new one before using the bot.
CURRENT_CONSENT_VERSION = "2026-10-16-v2"
CONSENT_EFFECTIVE_DATE = date.fromisoformat(CURRENT_CONSENT_VERSION[:10]).strftime("%d %B %Y")

CONSENT_CALLBACKS = {
    "consent:agree",
    "consent:terms",
    "consent:privacy",
}

POLICY_DIR = Path(__file__).resolve().parent.parent / "data" / "legal"

CONSENT_PROMPT = f"""
<b>CONQUEER — Terms &amp; Privacy</b>
Effective date: {CONSENT_EFFECTIVE_DATE}

CONQUEER is for adults aged 18 and over. By tapping <b>I Agree</b>, you confirm you are at least 18, accept the Terms of Service and Privacy Policy, and consent to the processing of the profile and sensitive personal data needed to operate the service.

Profiles, photos, approximate location, likes, matches and reports are processed to run matching and keep the community safe. Other users can see the profile details and photos you choose to share. We do not verify identities or conduct background checks, and meetings are at your own risk. You can request access, correction or deletion of your data through the contact in the Privacy Policy.

Please read both documents before agreeing. You cannot use the bot unless you agree.
""".strip()


def consent_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📄 Terms of Service", callback_data="consent:terms")
    builder.button(text="🔒 Privacy Policy", callback_data="consent:privacy")
    builder.button(text="✅ I Agree", callback_data="consent:agree")
    builder.adjust(2, 1)
    return builder.as_markup()


def has_current_consent(user: UserModel | None) -> bool:
    return bool(
        user
        and user.consent_version == CURRENT_CONSENT_VERSION
        and user.consented_at is not None
    )


async def show_consent(event: Message | CallbackQuery) -> None:
    if isinstance(event, Message):
        await event.answer(CONSENT_PROMPT, reply_markup=consent_keyboard())
        return

    await event.answer()
    await bot.send_message(
        chat_id=event.from_user.id,
        text=CONSENT_PROMPT,
        reply_markup=consent_keyboard(),
    )


async def require_consent(event: Message | CallbackQuery, user: UserModel | None) -> bool:
    """Return False and show the gate unless the user has accepted this version."""
    if has_current_consent(user):
        return True

    if isinstance(event, CallbackQuery) and event.data in CONSENT_CALLBACKS:
        return True

    await show_consent(event)
    return False


def _plain_policy(markdown: str) -> str:
    """Render the supplied Markdown policy as readable plain text for Telegram."""
    lines = []
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line or line == "---":
            lines.append("")
            continue
        if line.startswith("|"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if cells and all(re.fullmatch(r"[:\-\s]+", cell or "-") for cell in cells):
                continue
            line = " — ".join(cells)
        line = re.sub(r"^#{1,6}\s*", "", line)
        line = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
        line = re.sub(r"\*(.*?)\*", r"\1", line)
        line = re.sub(r"`(.*?)`", r"\1", line)
        if line.startswith("- "):
            line = f"• {line[2:]}"
        lines.append(line)
    return "\n".join(lines).strip()


def _split_policy(text: str, limit: int = 3600) -> list[str]:
    chunks = []
    remaining = text.strip()
    while len(remaining) > limit:
        split_at = remaining.rfind("\n", 0, limit)
        if split_at < limit // 2:
            split_at = remaining.rfind(" ", 0, limit)
        if split_at < limit // 2:
            split_at = limit
        chunks.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks


async def send_policy(event: CallbackQuery, policy: str) -> None:
    filename = "terms.md" if policy == "terms" else "privacy.md"
    title = "Terms of Service" if policy == "terms" else "Privacy Policy"
    content = (POLICY_DIR / filename).read_text(encoding="utf-8")
    chunks = _split_policy(_plain_policy(content))

    await event.answer()
    for index, chunk in enumerate(chunks, start=1):
        await bot.send_message(
            chat_id=event.from_user.id,
            text=f"{title} ({index}/{len(chunks)})\n\n{chunk}",
            parse_mode=None,
        )


class ConsentCheckMiddleware:
    """Gate callback handlers in routers that do not use the common user middleware."""

    async def __call__(self, handler, event: CallbackQuery, data: dict):
        from database.services.user import User

        user = data.get("user")
        if user is None:
            user = await User.get_by_id(data["session"], event.from_user.id)
        if not data.get("consent_gate_checked") and not await require_consent(event, user):
            return
        if user is not None:
            data["user"] = user
        data["consent_gate_checked"] = True
        return await handler(event, data)


class ExistingConsentUpdateMiddleware(BaseMiddleware):
    """Gate all messages and callbacks from existing users, including unmatched events."""

    async def __call__(self, handler, update, data: dict):
        from database.services.user import User

        if not isinstance(update, Update):
            return await handler(update, data)

        event = update.callback_query or update.message
        if event is None or event.from_user is None:
            return await handler(update, data)

        user = await User.get_with_profile(data["session"], event.from_user.id)
        if user is None:
            if isinstance(event, Message):
                command = (event.text or "").split(maxsplit=1)
                command = command[0].split("@", maxsplit=1)[0].lower() if command else ""
                if command != "/start":
                    await show_consent(event)
                    return
            return await handler(update, data)

        if user.status == UserStatus.Banned:
            return await handler(update, data)

        if not await require_consent(event, user):
            return
        data["user"] = user
        data["consent_gate_checked"] = True
        return await handler(update, data)
