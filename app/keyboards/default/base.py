from aiogram.types import ReplyKeyboardRemove

from .kb_generator import simple_kb_generator as kb_gen

del_kb = ReplyKeyboardRemove()

cancel_kb = kb_gen(["/cancel"])
start_kb = kb_gen(["/start"])
profile_kb = kb_gen(["🔄", "🖼", "✍️", "❌"], ["↩️"])


search_kb = kb_gen(["❤️", "📩", "👎"], ["💢"], ["💤"])
admin_kb = kb_gen(["📊 Statistics", "📨 Mailing"], ["📝 Logs"], ["↩️"])
match_kb = kb_gen(["❤️", "👎"], ["💢"], ["💤"])
return_to_menu_kb = kb_gen(["↩️"])


age_filter_kb = kb_gen(["↩️"])
hosting_kb = lambda: kb_gen(["Yes ✅", "No ❌"], ["Airbnb 🏨", "All 🌍"], ["↩️"])
