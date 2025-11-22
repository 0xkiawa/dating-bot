import asyncio
from database.connect import async_engine
from database.models.base import BaseModel

# Import all models so SQLAlchemy knows about them
from database.models.user import User
from database.models.profile import Profile

async def create_tables():
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(BaseModel.metadata.create_all)
        print("✅ Tables created successfully!")
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(create_tables())