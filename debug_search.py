import asyncio
from database.connect import async_session
from database.services.user import User
from database.services.search import search_profiles

async def debug_search():
    async with async_session() as session:
        # Get user 1
        user1 = await User.get_with_profile(session, 6687425348)
        profile1 = user1.profile
        
        print(f"User 1: {user1.id}")
        print(f"  Mode: {user1.current_mode}")
        print(f"  Gender: {profile1.gender}, Looking for: {profile1.find_gender}")
        print(f"  Age: {profile1.age}")
        print(f"  Location: {profile1.latitude}, {profile1.longitude}")
        print(f"  Active: {profile1.is_active}")
        print()
        
        # Get user 2
        user2 = await User.get_with_profile(session, 7455239037)
        profile2 = user2.profile
        
        print(f"User 2: {user2.id}")
        print(f"  Mode: {user2.current_mode}")
        print(f"  Gender: {profile2.gender}, Looking for: {profile2.find_gender}")
        print(f"  Age: {profile2.age}")
        print(f"  Location: {profile2.latitude}, {profile2.longitude}")
        print(f"  Active: {profile2.is_active}")
        print()
        
        # Try search WITHOUT mode filter
        print("Searching WITHOUT mode filter:")
        results = await search_profiles(session, profile1, user_mode=None)
        print(f"Found: {len(results)} profiles")
        print()
        
        # Try search WITH mode filter
        print("Searching WITH 'fun' mode filter:")
        results = await search_profiles(session, profile1, user_mode='fun')
        print(f"Found: {len(results)} profiles")

asyncio.run(debug_search())
