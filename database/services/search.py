import math
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from data.config import search
from database.models.complaint import CompleintStatus, ProfileCompleintsModel
from database.models.match import (
    DiscoveryDeliveryEventModel,
    InteractionDecisionModel,
    MatchModel,
    PairMatchModel,
)
from database.models.profile import ProfileModel
from database.models.user import UserBlockModel, UserModel
from utils.logging import logger


def haversine_distance(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    earth_radius: int | None = None,
) -> int:
    """Return the approximate distance between two coordinates in kilometers."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    a = min(1.0, max(0.0, a))
    return round(
        (earth_radius or search.EARTH_RADIUS)
        * 2
        * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    )


def calculate_age_range(age: int) -> int:
    """Calculate the automatic age range used when no saved range is set."""
    calculated_range = max(search.MIN_AGE_RANGE, age * search.AGE_RANGE_MULTIPLIER)
    return min(search.MAX_AGE_RANGE, round(calculated_range))


def build_role_matching_conditions(user_role: str, user_find_role: str):
    """Return the legacy role compatibility predicate, applied in both directions."""
    if user_find_role == "all":
        wants_candidate = True
    elif user_find_role == "verse":
        wants_candidate = ProfileModel.role == "verse"
    elif user_find_role == "top":
        wants_candidate = or_(ProfileModel.role == "top", ProfileModel.role == "verse")
    elif user_find_role == "bottom":
        wants_candidate = or_(ProfileModel.role == "bottom", ProfileModel.role == "verse")
    else:
        wants_candidate = True

    if user_role == "verse":
        candidate_wants_user = True
    elif user_role == "top":
        candidate_wants_user = ProfileModel.find_role.in_(("top", "verse", "all"))
    elif user_role == "bottom":
        candidate_wants_user = ProfileModel.find_role.in_(("bottom", "verse", "all"))
    else:
        candidate_wants_user = True

    if wants_candidate is True:
        return candidate_wants_user
    if candidate_wants_user is True:
        return wants_candidate
    return and_(wants_candidate, candidate_wants_user)


def get_match_reasons(
    viewer: ProfileModel,
    candidate: ProfileModel,
    mode: str | None = None,
    distance_km: int | None = None,
) -> list[str]:
    """Return up to two concise, factual match reasons for a profile card."""
    from loader import _

    reasons: list[str] = []
    shared = set(viewer.interests or []) & set(candidate.interests or [])
    if shared:
        reasons.append(_("You both like similar things"))

    viewer_wants_candidate = candidate.body_type in (viewer.preferred_body_types or [])
    candidate_wants_viewer = viewer.body_type in (candidate.preferred_body_types or [])
    if viewer_wants_candidate and candidate_wants_viewer:
        reasons.append(_("You fit each other’s body type preferences"))
    elif viewer_wants_candidate:
        reasons.append(_("Fits your body type preferences"))
    elif candidate_wants_viewer:
        reasons.append(_("You fit their body type preferences"))

    if mode == "dates":
        viewer_intent = viewer.dating_intent or "open"
        candidate_intent = candidate.dating_intent or "open"
        if viewer_intent == candidate_intent and viewer_intent != "open":
            reasons.append(_("You want the same kind of dating"))
        elif "open" in (viewer_intent, candidate_intent):
            reasons.append(_("Dating intentions may be compatible"))

    if distance_km is not None and distance_km <= 25:
        reasons.append(_("Nearby"))

    if not reasons:
        reasons.append(_("Fits your age and role preferences"))
    return reasons[:2]


def _match_score(viewer: ProfileModel, candidate: ProfileModel, distance_km: int, mode: str | None) -> int:
    shared_interests = set(viewer.interests or []) & set(candidate.interests or [])
    score = min(len(shared_interests), 5) * 5
    if candidate.body_type in (viewer.preferred_body_types or []):
        score += 4
    if viewer.body_type in (candidate.preferred_body_types or []):
        score += 3
    if mode == "dates":
        viewer_intent = viewer.dating_intent or "open"
        candidate_intent = candidate.dating_intent or "open"
        if viewer_intent == candidate_intent and viewer_intent != "open":
            score += 4
        elif "open" in (viewer_intent, candidate_intent):
            score += 2
    if distance_km <= 25:
        score += 2
    return score


async def search_profiles(
    session: AsyncSession,
    profile: ProfileModel,
    user_mode: str | None = None,
    hosting_filter: str | None = None,
    min_age: int | None = None,
    max_age: int | None = None,
    initial_distance: float = search.INITIAL_DISTANCE,
    max_distance: float = search.MAX_DISTANCE,
    radius_step: float = search.RADIUS_STEP,
    min_profiles: int = search.MIN_PROFILES,
    block_size: float = search.BLOCK_SIZE,
    earth_radius: int = search.EARTH_RADIUS,
    force_shuffle: bool = True,
) -> list[int]:
    """Find adult, mutually compatible profiles and rank them by saved preferences."""
    if (
        profile is None
        or not profile.is_active
        or profile.age < 18
        or profile.latitude is None
        or profile.longitude is None
    ):
        return []
    viewer_status = await session.scalar(
        select(UserModel.status).where(UserModel.id == profile.id)
    )
    if viewer_status is None or viewer_status == 0:
        return []

    automatic_range = calculate_age_range(profile.age)
    if min_age is not None and max_age is not None:
        age_min, age_max = max(18, min_age), min(99, max_age)
    else:
        age_min = max(18, profile.age - automatic_range)
        age_max = min(99, profile.age + automatic_range)

    if age_min > age_max or age_max < 18:
        return []

    search_limit = max_distance or search.MAX_DISTANCE
    initial_distance = initial_distance or search.INITIAL_DISTANCE
    radius_step = radius_step or search.RADIUS_STEP
    min_profiles = min_profiles or search.MIN_PROFILES
    block_size = block_size or search.BLOCK_SIZE

    mode = user_mode or "legacy"
    cooldown_cutoff = datetime.now(timezone.utc) - timedelta(
        days=search.REDISCOVERY_COOLDOWN_DAYS
    )
    active_decision = or_(
        InteractionDecisionModel.decision == "like",
        and_(
            InteractionDecisionModel.decision == "pass",
            InteractionDecisionModel.created_at > cooldown_cutoff,
        ),
    )
    mode_decisions = select(
        case(
            (InteractionDecisionModel.actor_id == profile.id, InteractionDecisionModel.target_id),
            else_=InteractionDecisionModel.actor_id,
        )
    ).where(
        or_(
            InteractionDecisionModel.actor_id == profile.id,
            InteractionDecisionModel.target_id == profile.id,
        ),
        InteractionDecisionModel.mode == mode,
        active_decision,
    )
    matched_users = select(
        case(
            (PairMatchModel.user_low_id == profile.id, PairMatchModel.user_high_id),
            else_=PairMatchModel.user_low_id,
        )
    ).where(
        PairMatchModel.mode.in_((mode, "legacy")),
        or_(PairMatchModel.user_low_id == profile.id, PairMatchModel.user_high_id == profile.id),
    )
    recent_deliveries = select(DiscoveryDeliveryEventModel.target_id).where(
        DiscoveryDeliveryEventModel.viewer_id == profile.id,
        DiscoveryDeliveryEventModel.mode == mode,
        DiscoveryDeliveryEventModel.status == "delivered",
        or_(
            and_(
                DiscoveryDeliveryEventModel.source == "search",
                DiscoveryDeliveryEventModel.delivered_at > cooldown_cutoff,
            ),
            and_(
                DiscoveryDeliveryEventModel.source == "shared",
                DiscoveryDeliveryEventModel.delivered_at
                > datetime.now(timezone.utc) - timedelta(days=21),
            ),
        ),
    )
    legacy_interactions = select(
        case(
            (MatchModel.sender_id == profile.id, MatchModel.receiver_id),
            else_=MatchModel.sender_id,
        )
    ).where(
        or_(MatchModel.sender_id == profile.id, MatchModel.receiver_id == profile.id),
        MatchModel.is_active.is_(True),
        or_(MatchModel.mode == "legacy", MatchModel.mode == mode),
    )
    reported_profiles = select(
        case(
            (ProfileCompleintsModel.sender_id == profile.id, ProfileCompleintsModel.receiver_id),
            else_=ProfileCompleintsModel.sender_id,
        )
    ).where(
        or_(
            ProfileCompleintsModel.sender_id == profile.id,
            ProfileCompleintsModel.receiver_id == profile.id,
        ),
        ProfileCompleintsModel.status.in_((CompleintStatus.Pending, CompleintStatus.Accepted)),
    )
    blocked_profiles = select(UserBlockModel.blocked_id).where(
        UserBlockModel.blocker_id == profile.id
    )
    blocked_by_profiles = select(UserBlockModel.blocker_id).where(
        UserBlockModel.blocked_id == profile.id
    )

    conditions = [
        ProfileModel.id != profile.id,
        ProfileModel.is_active.is_(True),
        ProfileModel.age >= 18,
        ProfileModel.age.between(age_min, age_max),
        build_role_matching_conditions(profile.role, profile.find_role),
        UserModel.status != 0,
        ProfileModel.id.not_in(mode_decisions),
        ProfileModel.id.not_in(matched_users),
        ProfileModel.id.not_in(recent_deliveries),
        ProfileModel.id.not_in(legacy_interactions),
        ProfileModel.id.not_in(reported_profiles),
        ProfileModel.id.not_in(blocked_profiles),
        ProfileModel.id.not_in(blocked_by_profiles),
    ]
    if user_mode:
        conditions.append(UserModel.current_mode == user_mode)
    if hosting_filter and hosting_filter != "all":
        conditions.append(ProfileModel.hosting == hosting_filter)

    result = await session.execute(
        select(ProfileModel).join(UserModel, ProfileModel.id == UserModel.id).where(and_(*conditions))
    )

    candidates: list[tuple[ProfileModel, int]] = []
    for candidate in result.scalars():
        if candidate.latitude is None or candidate.longitude is None:
            continue
        distance = haversine_distance(
            profile.latitude,
            profile.longitude,
            candidate.latitude,
            candidate.longitude,
            earth_radius=earth_radius,
        )
        if distance <= search_limit:
            candidates.append((candidate, distance))

    # Expand the effective radius until enough choices are available or the cap is reached.
    # Age, role, and hosting filters come from the current Browse Matches flow.
    radius = min(initial_distance, search_limit)
    while radius < search_limit and sum(distance <= radius for _, distance in candidates) < min_profiles:
        radius = min(radius + radius_step, search_limit)
    candidates = [(item, distance) for item, distance in candidates if distance <= radius]

    groups: dict[int, dict[int, list[tuple[ProfileModel, int]]]] = {}
    for candidate, distance in candidates:
        score = _match_score(profile, candidate, distance, user_mode)
        # Rank better preference fits first, then nearby distance blocks; shuffle ties.
        distance_bucket = int(distance // max(block_size, 1))
        groups.setdefault(score, {}).setdefault(distance_bucket, []).append((candidate, distance))

    if force_shuffle:
        for distance_groups in groups.values():
            for group in distance_groups.values():
                random.shuffle(group)

    ordered = [
        item
        for score in sorted(groups, reverse=True)
        for distance_bucket in sorted(groups[score])
        for item in groups[score][distance_bucket]
    ]
    logger.log(
        "DATABASE",
        f"User {profile.id} match search found {len(ordered)} adult profiles "
        f"within {radius}km (age {age_min}-{age_max}, mode={user_mode or 'any'}).",
    )
    return [candidate.id for candidate, _distance in ordered]
