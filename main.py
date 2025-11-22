import asyncio

from aiogram.methods import DeleteWebhook

from app.commands import set_default_commands
from app.handlers import setup_handlers
from app.middlewares import setup_middlewares
from data.config import tgbot
from loader import bot, dp
from utils.logging import logger


async def create_tables():
    """Create database tables if they don't exist"""
    try:
        from database.connect import async_engine
        from database.models.base import BaseModel
        # Just import the modules to register the models
        import database.models.user
        import database.models.profile
        
        logger.log("BOT", "Creating database tables...")
        async with async_engine.begin() as conn:
            await conn.run_sync(BaseModel.metadata.create_all)
        logger.log("BOT", "✅ Tables created successfully!")
    except Exception as e:
        logger.log("BOT", f"❌ Error creating tables: {e}")
        raise


async def on_startup() -> None:
    await set_default_commands()
    logger.log("BOT", "~ Bot startup")


async def on_shutdown() -> None:
    logger.log("BOT", "~ Bot shutting down...")


async def main():
    # Create tables before starting the bot
    await create_tables()
    
    setup_middlewares(dp)
    setup_handlers(dp)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    await bot(DeleteWebhook(drop_pending_updates=tgbot.SKIP_UPDATES))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())