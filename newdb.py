import asyncio
from database.connect import async_session
from database.models.user import UserModel
from database.models.profile import ProfileModel
from sqlalchemy import select, and_, or_

async def debug_search():
    """Debug why search returns 0 profiles"""
    async with async_session() as session:
        print("=" * 80)
        print("SEARCH DEBUG")
        print("=" * 80)
        
        # Get the searching user (6687425348)
        user_id = 6687425348
        result = await session.execute(
            select(UserModel, ProfileModel)
            .join(ProfileModel, UserModel.id == ProfileModel.id)
            .where(UserModel.id == user_id)
        )
        user_data = result.one_or_none()
        
        if not user_data:
            print(f"\n❌ User {user_id} not found!")
            return
        
        user, profile = user_data
        
        print(f"\n👤 SEARCHING USER:")
        print(f"  ID: {user.id}")
        print(f"  Name: {profile.name}")
        print(f"  Role: {profile.role}")
        print(f"  Find Role: {profile.find_role}")
        print(f"  Age: {profile.age}")
        print(f"  Mode: {user.current_mode}")
        print(f"  Active: {profile.is_active}")
        
        print(f"\n🔍 SEARCH CRITERIA:")
        print(f"  Looking for role: {profile.find_role}")
        print(f"  In mode: {user.current_mode}")
        print(f"  Age range: 5-41 (from log)")
        print(f"  Max distance: 10000km")
        
        print("\n" + "=" * 80)
        print("ALL OTHER PROFILES:")
        print("=" * 80)
        
        # Get all other profiles
        result = await session.execute(
            select(UserModel, ProfileModel)
            .join(ProfileModel, UserModel.id == ProfileModel.id)
            .where(ProfileModel.id != user_id)
        )
        other_profiles = result.all()
        
        print(f"\nFound {len(other_profiles)} other profiles:\n")
        
        for other_user, other_profile in other_profiles:
            print(f"  ID: {other_profile.id}")
            print(f"  Name: {other_profile.name}")
            print(f"  Role: {other_profile.role}")
            print(f"  Find Role: {other_profile.find_role}")
            print(f"  Age: {other_profile.age}")
            print(f"  Mode: {other_user.current_mode}")
            print(f"  Active: {other_profile.is_active}")
            print(f"  is_active type: {type(other_profile.is_active)}")
            print(f"  is_active value: {repr(other_profile.is_active)}")
            
            # Check match conditions
            print(f"\n  ✓ Match Analysis:")
            print(f"    - Is active? {other_profile.is_active == True}")
            print(f"    - Same mode? {other_user.current_mode == user.current_mode}")
            print(f"    - Role matches find_role? {other_profile.role == profile.find_role or profile.find_role == 'all'}")
            print(f"    - Find_role matches role? {other_profile.find_role == profile.role or other_profile.find_role == 'all'}")
            print(f"    - Not self? {other_profile.id != user_id}")
            
            all_match = (
                other_profile.is_active == True and
                other_user.current_mode == user.current_mode and
                (other_profile.role == profile.find_role or profile.find_role == 'all') and
                (other_profile.find_role == profile.role or other_profile.find_role == 'all') and
                other_profile.id != user_id
            )
            
            if all_match:
                print(f"    ✅ THIS PROFILE SHOULD MATCH!")
            else:
                print(f"    ❌ Does not match")
            
            print("-" * 40)
        
        print("\n" + "=" * 80)
        print("CHECKING DATABASE QUERY")
        print("=" * 80)
        
        # Try the actual query conditions
        result = await session.execute(
            select(ProfileModel)
            .join(UserModel, ProfileModel.id == UserModel.id)
            .where(
                and_(
                    ProfileModel.is_active == True,
                    UserModel.current_mode == user.current_mode,
                    ProfileModel.id != user_id,
                    or_(
                        ProfileModel.role == profile.find_role,
                        profile.find_role == 'all'
                    ),
                    or_(
                        ProfileModel.find_role == profile.role,
                        ProfileModel.find_role == 'all'
                    )
                )
            )
        )
        matching_profiles = result.scalars().all()
        
        print(f"\n📊 Query returned {len(matching_profiles)} matching profiles")
        
        if len(matching_profiles) == 0:
            print("\n❌ No matches found. Checking each condition separately:\n")
            
            # Check is_active
            result = await session.execute(
                select(ProfileModel).where(ProfileModel.is_active == True)
            )
            active = result.scalars().all()
            print(f"  Profiles where is_active == True: {len(active)}")
            
            # Check mode
            result = await session.execute(
                select(ProfileModel)
                .join(UserModel)
                .where(UserModel.current_mode == user.current_mode)
            )
            same_mode = result.scalars().all()
            print(f"  Profiles in '{user.current_mode}' mode: {len(same_mode)}")
            
            # Check not self
            result = await session.execute(
                select(ProfileModel).where(ProfileModel.id != user_id)
            )
            not_self = result.scalars().all()
            print(f"  Profiles that are not self: {len(not_self)}")
        
        print("\n" + "=" * 80)
        print("✅ Debug complete!")
        print("=" * 80)

if __name__ == "__main__":
    asyncio.run(debug_search())