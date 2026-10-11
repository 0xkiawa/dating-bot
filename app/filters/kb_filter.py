from aiogram.filters.callback_data import CallbackData


class LangCallback(CallbackData, prefix="lang"):
    lang: str


class BlockUserCallback(CallbackData, prefix="ban"):
    complaint_id: int
    receiver_id: int
    receiver_username: str | None
    ban: bool


class StatsCallback(CallbackData, prefix="stats"):
    type: str

class PhotoRevealCallback(CallbackData, prefix="reveal"):
    media_id: int

class CarouselNavCallback(CallbackData, prefix="carnav"):
    profile_id: int
    index: int


class MainMenuCallback(CallbackData, prefix="mainmenu"):
    action: str


class ModeSelectionCallback(CallbackData, prefix="modeselect"):
    mode: str


class ModeMenuCallback(CallbackData, prefix="modemenu"):
    action: str


class ModeConfirmCallback(CallbackData, prefix="modeconfirm"):
    switch: bool


class BrowseFilterCallback(CallbackData, prefix="browsefilter"):
    step: str
    value: str


class ProfileActionCallback(CallbackData, prefix="profileaction"):
    action: str
    profile_id: int
    value: str


class MatchPreferenceCallback(CallbackData, prefix="matchpref"):
    action: str
    value: str
