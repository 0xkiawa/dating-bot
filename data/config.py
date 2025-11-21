from pathlib import Path
from environs import Env

env = Env()
env.read_env()

# Project directory
DIR = Path(__file__).resolve().parent.parent

# Locales directory for translations
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
db = DatabaseSettings()