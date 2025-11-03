import asyncio
import logging
from database.services.profile import Profile
from database.services.search import search_profiles
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.DEBUG)

async def update_test_coordinates(session: AsyncSession):
    """Update profiles with test coordinates for distance testing"""
    # Test locations (roughly NYC and LA)
    locations = {
        6687425348: (40.7128, -74.0060),  # NYC
        7455239037: (34.0522, -118.2437)  # LA
    }
    
    for user_id, (lat, lon) in locations.items():
        await Profile.create_or_update(
            session,
            id=user_id,
            latitude=lat,
            longitude=lon
        )
    await session.commit()

async def test_search():
    engine = create_async_engine('sqlite+aiosqlite:///database/db.sqlite3')
    async_session = sessionmaker(engine, class_=AsyncSession)
    
    async with async_session() as session:
        # First update coordinates
        await update_test_coordinates(session)
        
        # Then search
        results = await search_profiles(session, user_id=6687425348)
        print(f'\nFound {len(results)} matches:')
        for r in results:
            print(
                f'ID: {r.profile.id}, '
                f'Age: {r.profile.age}, '
                f'Gender: {r.profile.gender}, '
                f'Location: ({r.profile.latitude:.4f}, {r.profile.longitude:.4f}), '
                f'Distance: {r.distance:.1f}km'
            )

if __name__ == '__main__':
    asyncio.run(test_search())