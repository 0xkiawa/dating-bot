from aiogram.types import Update
from aiogram.utils.i18n import I18nMiddleware

from app.locales import normalize_locale
from loader import i18n


class MyI18nMiddleware(I18nMiddleware):
    async def get_locale(self, event: Update, data: dict) -> str:
        user = data.get("user")
        language = getattr(user, "language", None)
        if language:
            return normalize_locale(language)

        return normalize_locale(await super().get_locale(event, data))


i18n_middleware = MyI18nMiddleware(i18n)
