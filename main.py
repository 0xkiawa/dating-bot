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
        from database.connect import async_engine, async_session
        from database.models.base import BaseModel
        from database.models.profile import ProfileModel
        from database.schema import ensure_profile_match_columns, ensure_user_consent_columns
        from sqlalchemy import update
        
        # Just import the modules to register the models
        import database.models.user
        import database.models.profile
        
        logger.log("BOT", "Creating database tables...")
        async with async_engine.begin() as conn:
            await conn.run_sync(BaseModel.metadata.create_all)
            await conn.run_sync(ensure_profile_match_columns)
            await conn.run_sync(ensure_user_consent_columns)
        logger.log("BOT", "✅ Tables created successfully!")
        
        # Existing profiles under 18 must not remain visible in discovery.
        async with async_session() as session:
            result = await session.execute(
                update(ProfileModel)
                .where(ProfileModel.age < 18)
                .where(ProfileModel.is_active.is_(True))
                .values(is_active=False)
            )
            await session.commit()
            logger.log(
                "BOT",
                f"Deactivated {result.rowcount or 0} profile(s) with age below 18.",
            )
        
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
