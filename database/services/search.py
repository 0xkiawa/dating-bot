import math
import random
import time

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from data.config import search
from database.models.profile import ProfileModel
from database.models.user import UserModel
from utils.logging import logger


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    """
    Returns approximate distance between two points (in kilometers)
    by latitude and longitude coordinates.
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return round(search.EARTH_RADIUS * c)


def calculate_age_range(age: int) -> int:
    """
    Calculates dynamic age range based on user's age.

    Formula: max(MIN_AGE_RANGE, age * AGE_RANGE_MULTIPLIER)
    Limits: minimum MIN_AGE_RANGE years, maximum MAX_AGE_RANGE years

    Examples:
    - 16 years → 3 years
    - 25 years → 4 years
    - 30 years → 5 years
    - 50 years → 8 years
    - 60+ years → 15 years (maximum)
    """
    calculated_range = max(search.MIN_AGE_RANGE, age * search.AGE_RANGE_MULTIPLIER)
    return min(search.MAX_AGE_RANGE, round(calculated_range))


def build_role_matching_conditions(user_role: str, user_find_role: str):
    """
    Build role matching conditions:
    - Top matches with Bottom and Verse
    - Bottom matches with Top and Verse
    - Verse matches with everyone (Top, Bottom, Verse)
    - "all" preference matches everyone
    """
    role_conditions = []
    
    # User's role matching logic
    if user_role == 'top':
        # Top looks for Bottom or Verse
        role_conditions.append(
            or_(
                ProfileModel.role == 'bottom',
                ProfileModel.role == 'verse'
            )
        )
    elif user_role == 'bottom':
        # Bottom looks for Top or Verse
        role_conditions.append(
            or_(
                ProfileModel.role == 'top',
                ProfileModel.role == 'verse'
            )
        )
    elif user_role == 'verse':
        # Verse matches with everyone
        role_conditions.append(
            or_(
                ProfileModel.role == 'top',
                ProfileModel.role == 'bottom',
                ProfileModel.role == 'verse'
            )
        )
    
    # What user is looking for
    if user_find_role == 'all':
        # Looking for everyone - no additional filter needed
        pass
    else:
        # Looking for specific role
        role_conditions.append(ProfileModel.role == user_find_role)
    
    # Check if other profile wants user's role
    find_role_condition = or_(
        ProfileModel.find_role == user_role,
        ProfileModel.find_role == 'verse',  # Verse matches with everyone
        ProfileModel.find_role == 'all',
    )
    role_conditions.append(find_role_condition)
    
    return and_(*role_conditions) if role_conditions else True


async def search_profiles(
    session: AsyncSession,
    profile: ProfileModel,
    user_mode: str = None,
    hosting_filter: str = None,
    min_age: int = None,  # NEW: minimum age filter
    max_age: int = None,  # NEW: maximum age filter
    initial_distance: float = search.INITIAL_DISTANCE,
    max_distance: float = search.MAX_DISTANCE,
    radius_step: float = search.RADIUS_STEP,
    min_profiles: int = search.MIN_PROFILES,
    block_size: float = search.BLOCK_SIZE,
    earth_radius: int = search.EARTH_RADIUS,
    force_shuffle: bool = True,
) -> list:
    """
    Dynamic profile search: starts with small radius and increases until enough profiles found.
    Uses smart age range calculation and block-based shuffling.
    Filters by matching mode (fun/dates/friends), role compatibility, hosting preference, and age range.

    Args:
        session: Database session
        profile: User profile for search
        user_mode: Current user mode (fun/dates/friends)
        hosting_filter: Hosting filter (yes/no/airbnb/all)
        min_age: Minimum age filter (user preference) - NEW
        max_age: Maximum age filter (user preference) - NEW
        initial_distance: Initial search distance (km)
        max_distance: Maximum search distance (km)
        radius_step: Radius increase step (km)
        min_profiles: Minimum number of profiles to find
        block_size: Block size for shuffling (km)
        earth_radius: Earth radius in km
        force_shuffle: Force shuffle on every call
    """

    # Check that profile exists and has necessary data
    if not profile:
        return []

    if not profile.latitude or not profile.longitude:
        return []

    # Use provided parameters or default values from config
    initial_distance = initial_distance or search.INITIAL_DISTANCE
    max_distance = max_distance or search.MAX_DISTANCE
    radius_step = radius_step or search.RADIUS_STEP
    min_profiles = min_profiles or search.MIN_PROFILES
    block_size = block_size or search.BLOCK_SIZE
    earth_radius = earth_radius or search.EARTH_RADIUS

    # NEW: Calculate age range - use custom if provided, otherwise use dynamic calculation
    if min_age is not None and max_age is not None:
        # User has set custom age range
        age_min = min_age
        age_max = max_age
        age_filter_type = "custom"
    else:
        # Use dynamic age range based on user's age
        dynamic_age_range = calculate_age_range(profile.age)
        age_min = profile.age - dynamic_age_range
        age_max = profile.age + dynamic_age_range
        age_filter_type = "auto"

    found_profiles = []
    current_distance = initial_distance

    while current_distance <= max_distance and len(found_profiles) < min_profiles:
        # Distance calculation using CASE for clamping (SQLite compatible)
        cos_calc = (
            func.cos(func.radians(profile.latitude))
            * func.cos(func.radians(ProfileModel.latitude))
            * func.cos(
                func.radians(ProfileModel.longitude) - func.radians(profile.longitude)
            )
            + func.sin(func.radians(profile.latitude))
            * func.sin(func.radians(ProfileModel.latitude))
        )

        # Clamp value between -1 and 1 using CASE (SQLite compatible)
        clamped = case(
            (cos_calc > 1.0, 1.0),
            (cos_calc < -1.0, -1.0),
            else_=cos_calc
        )

        distance_expr = func.acos(clamped) * earth_radius

        # Build role matching conditions
        role_matching = build_role_matching_conditions(profile.role, profile.find_role)

        # Base query conditions
        conditions = [
            ProfileModel.is_active == 'True',
            distance_expr < current_distance,
            role_matching,  # Role-based matching
            ProfileModel.age.between(age_min, age_max),  # UPDATED: Use calculated age range
            ProfileModel.id != profile.id,
        ]

        # Add mode filter if user has active mode
        if user_mode:
            conditions.append(UserModel.current_mode == user_mode)

        # Add hosting filter
        if hosting_filter and hosting_filter != 'all':
            conditions.append(ProfileModel.hosting == hosting_filter)

        stmt = (
            select(ProfileModel.id, distance_expr.label("distance"))
            .join(UserModel, ProfileModel.id == UserModel.id)
            .where(and_(*conditions))
            .order_by(distance_expr)
        )

        result = await session.execute(stmt)
        found_profiles = result.fetchall()

        # If few profiles found - increase radius and try again
        current_distance += radius_step

    # Split into blocks and shuffle
    blocks = {}
    for id, dist in found_profiles:
        block_key = int(dist // block_size)
        blocks.setdefault(block_key, []).append(id)

    # Shuffle profiles within each block
    if force_shuffle:
        random.seed(int(time.time() * 1000000) % 2147483647)

    for key in blocks:
        random.shuffle(blocks[key])

    # Collect sorted by blocks list with shuffled content
    id_list = [id for key in sorted(blocks.keys()) for id in blocks[key]]

    mode_info = f" in {user_mode} mode" if user_mode else ""
    hosting_info = f" (hosting: {hosting_filter})" if hosting_filter and hosting_filter != 'all' else ""
    age_info = f" (age: {age_min}-{age_max} [{age_filter_type}])"  # NEW: Show age range and type
    
    logger.log(
        "DATABASE",
        f"User {profile.id} ({profile.role} looking for {profile.find_role}{age_info}){mode_info}{hosting_info} found {len(id_list)} profiles "
        f"in radius {current_distance - radius_step:.1f}km, shuffled={'Yes' if force_shuffle else 'No'}",
    )

    return id_list