from aiogram import Router

from app.middlewares.admin import AdminMiddleware

dating_router = Router()
voide_router = Router()
common_router = Router()
admin_router = Router()

# Gate every message on admin_router behind the admin check.
# Without this line, AdminMiddleware exists but is never actually applied,
# meaning /mailing (and every other admin command) would be open to anyone.
admin_router.message.middleware(AdminMiddleware())