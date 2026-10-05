from .profile import dating_router
from .search import dating_router
from .inbox import dating_router
from .create_profile import dating_router
from .edit_description import dating_router
from .edit_photo import dating_router
from .disable_profile import dating_router
from .form_errors import dating_router
from .mode_switch import dating_router
from .mode_selection import dating_router
from .age_filter import dating_router  # NEW: Add age filter handler
from .photo_reveal import dating_router # NEW: Add photo reveal handler
from .carousel_nav import dating_router  # NEW: Add carousel navigation handler
from .photo_privacy import dating_router  # NEW: Add photo privacy handler

__all__ = ["dating_router"]