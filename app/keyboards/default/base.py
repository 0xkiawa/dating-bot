from aiogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove

from loader import _

from .kb_generator import simple_kb_generator as kb_gen

del_kb = ReplyKeyboardRemove()

cancel_kb = kb_gen(["/cancel"])
start_kb = kb_gen(["/start"])
profile_kb = kb_gen(["🔄", "🖼", "✍️", "❌"], ["↩️"])
menu_kb = kb_gen(["👤", "✉️"], ["🎭"])


def mode_selection_kb() -> ReplyKeyboardMarkup:
    return kb_gen(
        [f"🍆👅🍑💦 {_('Fun Mode') }"],
        [f"❤️🥂 {_('Dating Mode') }"],
        [f"🤝 {_('Friends Mode') }"],
        ["↩️"],
    )


def mode_menu_kb() -> ReplyKeyboardMarkup:
    return kb_gen(
        [f"🔍 {_('Browse')}", f"📭 {_('Likes')}"],
        [f"🎂 {_('Age Filter')}", f"🏠 {_('Hosting')}"],
        [f"💤 {_('Menu')}"],
    )


search_kb = kb_gen(["❤️", "📩", "👎"], ["💢"], ["💤"])
admin_kb = kb_gen(["📊 Statistics", "📨 Mailing"], ["📝 Logs"], ["↩️"])
match_kb = kb_gen(["❤️", "👎"], ["💢"], ["💤"])
return_to_menu_kb = kb_gen(["↩️"])


def mode_confirm_kb() -> ReplyKeyboardMarkup:
    return kb_gen([f"✅ {_('Yes, Switch')}", f"❌ {_('No, Stay')}"])


age_filter_kb = kb_gen(["↩️"])
hosting_kb = lambda: kb_gen(["Yes ✅", "No ❌"], ["Airbnb 🏨", "All 🌍"], ["↩️"])