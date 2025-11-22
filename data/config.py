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

# Graph file path for statistics
GRAPH_FILE_PATH = DIR / "utils" / "graph.png"

# Logo directory
LOGO_DIR = DIR / "images" / "logo.png"


class TgBot:
    """Telegram Bot settings"""
    BOT_TOKEN: str = env.str("BOT_TOKEN")
    ADMIN_IDS: list[int] = env.list("ADMIN_IDS", [], subcast=int)
    MODERATOR_GROUP_ID: int = env.int("MODERATOR_GROUP_ID", default=None)
    NEW_USER_ALET_TO_GROUP: bool = env.bool("NEW_USER_ALERT_TO_GROUP", default=False)
    SKIP_UPDATES: bool = env.bool("SKIP_UPDATES", default=True)
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
    MIN_AGE_RANGE: int = env.int("MIN_AGE_RANGE", default=5)
    MAX_AGE_RANGE: int = env.int("MAX_AGE_RANGE", default=15)
    AGE_RANGE_MULTIPLIER: float = env.float("AGE_RANGE_MULTIPLIER", default=0.2)
    DISTANCE_INCREMENT: float = env.float("DISTANCE_INCREMENT", default=10.0)
    RADIUS_STEP: float = env.float("RADIUS_STEP", default=10.0)
    MIN_PROFILES: int = env.int("MIN_PROFILES", default=10)
    BLOCK_SIZE: float = env.float("BLOCK_SIZE", default=50.0)
    EARTH_RADIUS: int = env.int("EARTH_RADIUS", default=6371)
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
database = db  # Alias for backwards compatibility