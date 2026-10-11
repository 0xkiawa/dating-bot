from app.routers import admin_router

# Import modules for their router registrations. Some global admin commands are
# registered on common_router and therefore do not export admin_router themselves.
from . import admin, ban, logs, mailing, profile, restart, stats  # noqa: F401

__all__ = ["admin_router"]
