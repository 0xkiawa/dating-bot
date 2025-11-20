from pathlib import Path

from environs import Env

DIR = Path(__file__).absolute().parent.parent

env = Env()
env.read_env()


# -< Database >-
class DatabaseSettings:
    NAME: str = env.str("DB_NAME", default=None)
    HOST: str = env.str("DB_HOST", default=None)
    PORT: int = env.int("DB_PORT", default=None)
    USER: str = env.str("DB_USER", default=None)
    PASS: str = env.str("DB_PASS", default=None)

    # Use DB_URL if provided (Railway), otherwise build from individual vars
    _db_url = env.str("DB_URL", default=None)
    
    if _db_url:
        URL: str = _db_url
    elif all((NAME, HOST, PORT, USER, PASS)):
        URL: str = f"postgresql+asyncpg://{USER}:{PASS}@{HOST}:{PORT}/{NAME}"
    else:
        URL: str = f"sqlite+aiosqlite:///{DIR}/database/db.sqlite3"

    ECHO = False
    POOL_SIZE = 5
    MAX_OVERFLOW = 10


# -< Redis >-
class RedisSettings:
    DB: int = env.int("REDIS_DB", default=5)
    HOST: str = env.str("REDIS_HOST", default=None)
    PORT: int = env.int("REDIS_PORT", default=6379)
    USER: str = env.str("REDIS_USER", default=None)
    PASS: str = env.str("REDIS_PASS", default=None)

    _rd_url = env.str("RD_URL", default=None)
    
    if _rd_url:
        URL: str = _rd_url
    elif HOST and all((DB, HOST, PORT)):
        if all((USER, PASS)):
            URL: str = f"redis://{USER}:{PASS}@{HOST}:{PORT}/{DB}"
        else:
            URL: str = f"redis://{HOST}:{PORT}/{DB}"
    else:
        URL: str = None


# -< Telegram bot >-
class TelegramBotSettings:
    BOT_TOKEN: str = env.str("TELEGRAM_BOT_TOKEN", default=None)
    SKIP_UPDATES: bool = env.bool("SKIP_UPDATES", default=False)
    NEW_USER_ALET_TO_GROUP: bool = env.bool("NEW_USER_ALET_TO_GROUP", default=True)

    ADMINS: list = env.list("ADMINS", default=None, subcast=int)
    MODERATOR_GROUP_ID: int = env.int("MODERATOR_GROUP_ID", default=None)
    BOT_CHANNEL_URL: str = env.str("BOT_CHANNEL_URL", default=None)

    TIME_ZONE = "UTC"

    I18N_DOMAIN = "bot"


# -< Search >-
class SearchSettings:
    INITIAL_DISTANCE: float = env.float("INITIAL_DISTANCE", default=200.0)
    MAX_DISTANCE: float = env.float("MAX_DISTANCE", default=10000.0)
    RADIUS_STEP: float = env.float("RADIUS_STEP", default=200.0)
    MIN_PROFILES: int = env.int("MIN_PROFILES", default=100)
    EARTH_RADIUS: int = env.int("EARTH_RADIUS", default=6371)
    BLOCK_SIZE: float = env.float("BLOCK_SIZE", default=15.0)

    AGE_RANGE_MULTIPLIER: float = env.float("AGE_RANGE_MULTIPLIER", default=0.15)
    MIN_AGE_RANGE: int = env.int("MIN_AGE_RANGE", default=2)
    MAX_AGE_RANGE: int = env.int("MAX_AGE_RANGE", default=15)


# -< Path\Dir >-
IMAGES_DIR: Path = DIR / "images"
LOGO_DIR = f"{IMAGES_DIR}/logo.png"

GRAPH_FILE_PATH: Path = IMAGES_DIR / "stats_graph.png"

LOCALES_DIR: Path = DIR / "data" / "locales"

LOG_FILE_PATH: Path = DIR / "logs" / "logs.log"

# -< Other >-
database = DatabaseSettings()
redis = RedisSettings()
tgbot = TelegramBotSettings()
search = SearchSettings()
