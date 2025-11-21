from pathlib import Path
from environs import Env

env = Env()
env.read_env()

# Project directory
DIR = Path(__file__).resolve().parent.parent

# Locales directory for translations (it's inside data folder)
LOCALES_DIR = DIR / "data" / "locales"

# Log file path
LOG_FILE_PATH = DIR / "logs" / "bot.log"


class TgBot:
    """Telegram Bot settings"""
    BOT_TOKEN: str = env.str("BOT_TOKEN")
    ADMIN_IDS: list[int] = env.list("ADMIN_IDS", [], subcast=int)
    I18N_DOMAIN: str = env.str("I18N_DOMAIN", default="messages")


class RedisSettings:
    """Redis settings for FSM storage"""
    URL: str = env.str("REDIS_URL", default=None)


class SearchSettings:
    """Search settings for matching profiles"""
    INITIAL_DISTANCE: float = env.float("INITIAL_DISTANCE", default=50.0)
    MAX_DISTANCE: float = env.float("MAX_DISTANCE", default=100.0)
    MAX_DISTANCE_KM: int = env.int("MAX_DISTANCE_KM", default=100)
    MAX_AGE_DIFFERENCE: int = env.int("MAX_AGE_DIFFERENCE", default=10)
    DISTANCE_INCREMENT: float = env.float("DISTANCE_INCREMENT", default=10.0)
    RADIUS_STEP: float = env.float("RADIUS_STEP", default=10.0)
    MIN_PROFILES: int = env.int("MIN_PROFILES", default=10)
    BLOCK_SIZE: float = env.float("BLOCK_SIZE", default=50.0)
    MAX_RETRIES: int = env.int("MAX_SEARCH_RETRIES", default=5)

class DatabaseSettings:
    NAME: str = env.str("DB_NAME", default=None)
    HOST: str = env.str("DB_HOST", default=None)
    PORT: int = env.int("DB_PORT", default=None)
    USER: str = env.str("DB_USER", default=None)
    PASS: str = env.str("DB_PASS", default=None)

    # Use DB_URL if provided (Railway), otherwise build from individual vars
    _db_url = env.str("DB_URL", default=None)
    
    if _db_url:
        # Clean up the URL and ensure it uses asyncpg
        _db_url = _db_url.strip()  # Remove any whitespace/newlines
        if _db_url.startswith("postgresql://"):
            _db_url = _db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif _db_url.startswith("postgres://"):
            _db_url = _db_url.replace("postgres://", "postgresql+asyncpg://", 1)
        URL: str = _db_url
    elif all((NAME, HOST, PORT, USER, PASS)):
        URL: str = f"postgresql+asyncpg://{USER}:{PASS}@{HOST}:{PORT}/{NAME}"
    else:
        URL: str = f"sqlite+aiosqlite:///{DIR}/database/db.sqlite3"

    ECHO = False
    POOL_SIZE = 5
    MAX_OVERFLOW = 10


# Create instances
tgbot = TgBot()
redis = RedisSettings()
search = SearchSettings()
db = DatabaseSettings()