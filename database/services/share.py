import re
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database.models.profile import ProfileModel
from database.models.share import PendingSharedViewModel, ShareLinkModel
from database.models.user import UserBlockModel, UserModel, UserStatus

ADJECTIVES = (
    "velvet", "bold", "golden", "midnight", "electric", "neon", "silky", "wild",
    "royal", "cheeky", "smooth", "daring", "glossy", "cosmic", "fearless", "smoky",
    "honey", "spicy", "rosy", "flirty", "sunset", "rebel",
)
NOUNS = (
    "lion", "king", "prince", "panther", "tiger", "wolf", "fox", "stallion",
    "phoenix", "flame", "knight", "jaguar", "falcon", "comet", "ember", "storm",
    "crown", "rogue", "hunter", "wave",
)
RESERVED_SLUGS = frozenset(
    {"admin", "support", "conqueer", "help", "start", "bot", "official", "mod", "moderator"}
)
SLUG_PATTERN = re.compile(r"^[a-z]+-[a-z]+(?:-[0-9]{1,2})?$")
PENDING_VIEW_TTL = timedelta(days=14)
REROLL_LIMIT = 3
REROLL_WINDOW = timedelta(hours=24)


def _utc_naive_now() -> datetime:
    """Return UTC wall time for BaseModel.created_at (timestamp without time zone)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ShareRerollLimitError(Exception):
    """Raised when an owner has used all allowed link changes for the day."""


def generate_share_slug() -> str:
    """Choose a readable, non-identifying word pair for a profile link."""
    return f"{secrets.choice(ADJECTIVES)}-{secrets.choice(NOUNS)}"


def is_valid_share_slug(slug: str) -> bool:
    if not SLUG_PATTERN.fullmatch(slug):
        return False
    return not any(part in RESERVED_SLUGS for part in slug.split("-"))


def insert_shared_profile(profile_ids: list[int], target_id: int) -> list[int]:
    """Place a referred profile third, or last when fewer than two others exist."""
    ordered = [profile_id for profile_id in profile_ids if profile_id != target_id]
    index = 2 if len(ordered) >= 2 else len(ordered)
    ordered.insert(index, target_id)
    return ordered


def get_share_start_payload(message_text: str | None) -> str | None:
    """Extract a Telegram /start payload, leaving existing usr_ referrals alone."""
    parts = (message_text or "").split(maxsplit=1)
    if not parts or parts[0].split("@", maxsplit=1)[0].lower() != "/start":
        return None
    if len(parts) < 2:
        return None
    payload = parts[1].split(maxsplit=1)[0]
    if payload.startswith("usr_"):
        return None
    return payload if is_valid_share_slug(payload) else None


async def _cleanup_old_pending(session: AsyncSession) -> None:
    # PendingSharedViewModel.created_at comes from BaseModel and is stored as
    # TIMESTAMP WITHOUT TIME ZONE in PostgreSQL. Bind a naive UTC value so
    # asyncpg does not reject an aware datetime for that column.
    cutoff = _utc_naive_now() - PENDING_VIEW_TTL
    await session.execute(
        update(PendingSharedViewModel)
        .where(
            PendingSharedViewModel.status == "pending",
            PendingSharedViewModel.created_at < cutoff,
        )
        .values(status="expired")
    )
    # Keep share-click records for no longer than the 14-day period described
    # in the Privacy Policy. The status update still makes expiry explicit.
    await session.execute(
        delete(PendingSharedViewModel).where(PendingSharedViewModel.created_at < cutoff)
    )


async def cleanup_expired_shared_views(session: AsyncSession) -> None:
    """Expire pending share clicks and delete click records older than 14 days."""
    await _cleanup_old_pending(session)
    await session.commit()


async def _choose_unused_slug(session: AsyncSession) -> str:
    for _attempt in range(100):
        pair = generate_share_slug()
        suffix = ""
        if await session.scalar(
            select(ShareLinkModel.user_id).where(ShareLinkModel.slug == pair)
        ):
            suffix = f"-{secrets.randbelow(99) + 1}"
        candidate = pair + suffix
        if is_valid_share_slug(candidate) and not await session.scalar(
            select(ShareLinkModel.user_id).where(ShareLinkModel.slug == candidate)
        ):
            return candidate
    raise RuntimeError("Could not allocate a unique share slug")


async def issue_or_reroll_share_link(
    session: AsyncSession, user_id: int, *, reroll: bool = False
) -> ShareLinkModel:
    user = await session.scalar(
        select(UserModel)
        .options(joinedload(UserModel.profile))
        .where(UserModel.id == user_id)
    )
    if (
        not user
        or user.status == UserStatus.Banned
        or not user.profile
        or not user.profile.is_active
    ):
        raise ValueError("An active profile is required to share it")

    link = await session.scalar(
        select(ShareLinkModel).where(ShareLinkModel.user_id == user_id).with_for_update()
    )
    now = datetime.now(timezone.utc)
    if link and not reroll:
        return link

    if link and reroll:
        window_started = link.reroll_window_started_at
        if window_started and window_started.tzinfo is None:
            window_started = window_started.replace(tzinfo=timezone.utc)
        if window_started and now - window_started < REROLL_WINDOW:
            next_count = link.reroll_count + 1
            if next_count > REROLL_LIMIT:
                raise ShareRerollLimitError
        else:
            next_count = 1
            window_started = now
    else:
        next_count = 0
        window_started = None

    for _attempt in range(10):
        candidate = await _choose_unused_slug(session)
        if link:
            link.slug = candidate
            link.is_enabled = True
            link.reroll_count = next_count
            link.reroll_window_started_at = window_started
            await session.execute(
                update(PendingSharedViewModel)
                .where(
                    PendingSharedViewModel.target_id == user_id,
                    PendingSharedViewModel.status == "pending",
                )
                .values(status="expired")
            )
        else:
            link = ShareLinkModel(
                user_id=user_id,
                slug=candidate,
                is_enabled=True,
                reroll_count=0,
            )
            session.add(link)
        try:
            await session.commit()
            await session.refresh(link)
            return link
        except IntegrityError:
            await session.rollback()
            link = await session.scalar(
                select(ShareLinkModel)
                .where(ShareLinkModel.user_id == user_id)
                .with_for_update()
            )
            # A concurrent first-time confirmation already created the link.
            if link and not reroll:
                return link
    raise RuntimeError("Could not save a unique share link")


async def disable_share_link(session: AsyncSession, user_id: int) -> bool:
    link = await session.get(ShareLinkModel, user_id)
    if not link:
        return False
    link.is_enabled = False
    await expire_pending_shared_views_for_target(session, user_id)
    await session.commit()
    return True


async def expire_pending_shared_views_for_target(
    session: AsyncSession, user_id: int
) -> None:
    await session.execute(
        update(PendingSharedViewModel)
        .where(
            PendingSharedViewModel.target_id == user_id,
            PendingSharedViewModel.status == "pending",
        )
        .values(status="expired")
    )


async def resolve_share_slug(session: AsyncSession, slug: str) -> UserModel | None:
    if not is_valid_share_slug(slug):
        return None
    return await session.scalar(
        select(UserModel)
        .join(ShareLinkModel, ShareLinkModel.user_id == UserModel.id)
        .join(ProfileModel, ProfileModel.id == UserModel.id)
        .options(joinedload(UserModel.profile))
        .where(
            ShareLinkModel.slug == slug,
            ShareLinkModel.is_enabled.is_(True),
            UserModel.status != UserStatus.Banned,
            ProfileModel.is_active.is_(True),
            ProfileModel.age >= 18,
        )
    )


async def save_pending_shared_view(
    session: AsyncSession, viewer_id: int, target_id: int
) -> None:
    """Atomically replace the viewer's pending share click with the latest one."""
    await _cleanup_old_pending(session)
    now = _utc_naive_now()
    values = {
        "viewer_id": viewer_id,
        "target_id": target_id,
        "status": "pending",
        "created_at": now,
        "consumed_at": None,
    }
    dialect = session.get_bind().dialect.name
    if dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert

        statement = insert(PendingSharedViewModel).values(**values)
    elif dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert

        statement = insert(PendingSharedViewModel).values(**values)
    else:
        statement = None

    if statement is not None:
        statement = statement.on_conflict_do_update(
            index_elements=[PendingSharedViewModel.viewer_id],
            index_where=PendingSharedViewModel.status == "pending",
            set_={
                "target_id": target_id,
                "created_at": now,
                "consumed_at": None,
            },
        )
        await session.execute(statement)
    else:
        existing = await session.scalar(
            select(PendingSharedViewModel)
            .where(
                PendingSharedViewModel.viewer_id == viewer_id,
                PendingSharedViewModel.status == "pending",
            )
            .with_for_update()
        )
        if existing:
            existing.target_id = target_id
            existing.created_at = now
            existing.consumed_at = None
        else:
            session.add(PendingSharedViewModel(**values))
    await session.commit()


async def get_pending_shared_view(
    session: AsyncSession, viewer_id: int
) -> PendingSharedViewModel | None:
    await _cleanup_old_pending(session)
    await session.commit()
    return await session.scalar(
        select(PendingSharedViewModel).where(
            PendingSharedViewModel.viewer_id == viewer_id,
            PendingSharedViewModel.status == "pending",
        )
    )


async def shared_target_is_eligible(
    session: AsyncSession, viewer_id: int, target_id: int
) -> UserModel | None:
    if viewer_id == target_id:
        return None
    target = await session.scalar(
        select(UserModel)
        .options(joinedload(UserModel.profile))
        .where(UserModel.id == target_id)
    )
    if (
        not target
        or target.status == UserStatus.Banned
        or not target.profile
        or not target.profile.is_active
        or target.profile.age < 18
        or target.current_mode not in {"fun", "dates", "friends"}
    ):
        return None
    if not await session.scalar(
        select(ShareLinkModel.user_id).where(
            ShareLinkModel.user_id == target_id,
            ShareLinkModel.is_enabled.is_(True),
        )
    ):
        return None
    blocked = await session.scalar(
        select(UserBlockModel.id).where(
            or_(
                (UserBlockModel.blocker_id == viewer_id)
                & (UserBlockModel.blocked_id == target_id),
                (UserBlockModel.blocker_id == target_id)
                & (UserBlockModel.blocked_id == viewer_id),
            )
        )
    )
    return None if blocked else target


async def get_pending_shared_target(
    session: AsyncSession, viewer_id: int
) -> tuple[PendingSharedViewModel, UserModel] | None:
    pending = await get_pending_shared_view(session, viewer_id)
    if not pending:
        return None
    target = await shared_target_is_eligible(session, viewer_id, pending.target_id)
    return (pending, target) if target else None


async def consume_pending_shared_view(
    session: AsyncSession, pending_id: int | None
) -> bool:
    if pending_id is None:
        return False
    result = await session.execute(
        update(PendingSharedViewModel)
        .where(
            PendingSharedViewModel.id == pending_id,
            PendingSharedViewModel.status == "pending",
        )
        .values(status="consumed", consumed_at=datetime.now(timezone.utc))
    )
    await session.commit()
    return result.rowcount == 1
