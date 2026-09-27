from loader import i18n


def normalize_locale(language: str | None) -> str:
    """Return a supported base locale, falling back to the bot default."""
    if not language:
        return i18n.default_locale
    normalized = language.replace("_", "-").split("-", maxsplit=1)[0].lower()
    return normalized if normalized in i18n.available_locales else i18n.default_locale
