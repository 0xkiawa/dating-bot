from data.config import tgbot


def is_admin_id(user_id: int) -> bool:
    return user_id in tgbot.ADMIN_IDS
