import math
import random
from datetime import datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from data.config import search
from database.models.complaint import CompleintStatus, ProfileCompleintsModel
from database.models.match import MatchModel, MatchStatus
from database.models.profile import ProfileModel
from database.models.user import UserModel
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
    score = min(len(shared_interests), 3) * 3
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
        or profile.age < 18
        or profile.latitude is None
        or profile.longitude is None
    ):
        return []

    automatic_range = calculate_age_range(profile.age)
    saved_age_preference = (
        profile.preferred_age_min is not None
        or profile.preferred_age_max is not None
    )
    if min_age is not None and max_age is not None:
        age_min, age_max = max(18, min_age), min(99, max_age)
        if saved_age_preference:
            age_min = max(age_min, profile.preferred_age_min or 18)
            age_max = min(age_max, profile.preferred_age_max or 99)
    elif saved_age_preference:
        age_min = max(18, profile.preferred_age_min or 18)
        age_max = profile.preferred_age_max or 99
    else:
        age_min = max(18, profile.age - automatic_range)
        age_max = min(99, profile.age + automatic_range)

    if age_min > age_max or age_max < 18:
        return []

    search_limit = min(
        max_distance or search.MAX_DISTANCE,
        profile.preferred_distance_km or max_distance or search.MAX_DISTANCE,
    )
    initial_distance = initial_distance or search.INITIAL_DISTANCE
    radius_step = radius_step or search.RADIUS_STEP
    min_profiles = min_profiles or search.MIN_PROFILES
    block_size = block_size or search.BLOCK_SIZE

    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    recent_swipes = select(MatchModel.receiver_id).where(
        MatchModel.sender_id == profile.id,
        MatchModel.is_active.is_(True),
        or_(
            MatchModel.status != MatchStatus.Rejected,
            and_(
                MatchModel.status == MatchStatus.Rejected,
                MatchModel.updated_at >= thirty_days_ago,
            ),
        ),
    )
    reported_profiles = select(ProfileCompleintsModel.receiver_id).where(
        ProfileCompleintsModel.sender_id == profile.id,
        ProfileCompleintsModel.status.in_(
            (CompleintStatus.Pending, CompleintStatus.Accepted)
        ),
    )

    conditions = [
        ProfileModel.id != profile.id,
        ProfileModel.is_active.is_(True),
        ProfileModel.age >= 18,
        ProfileModel.age.between(age_min, age_max),
        build_role_matching_conditions(profile.role, profile.find_role),
        or_(ProfileModel.preferred_age_min.is_(None), ProfileModel.preferred_age_min <= profile.age),
        or_(ProfileModel.preferred_age_max.is_(None), ProfileModel.preferred_age_max >= profile.age),
        ProfileModel.id.not_in(recent_swipes),
        ProfileModel.id.not_in(reported_profiles),
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
        candidate_limit = min(
            search_limit,
            candidate.preferred_distance_km or search_limit,
        )
        if distance <= candidate_limit:
            candidates.append((candidate, distance))

    # Expand the effective radius until enough choices are available or the cap is reached.
    # Candidate distances are already filtered against both people's saved distance limits.
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
