import asyncio
from database.connect import async_engine
from database.models.base import BaseModel

async def create_tables():
    async with async_engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.create_all)
    print("✅ Tables created with role fields!")

asyncio.run(create_tables())
exit()