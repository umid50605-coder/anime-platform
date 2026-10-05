"""
All ORM models must be imported here so that Base.metadata is complete for
Alembic autogenerate and for `Base.metadata.create_all()` in tests.
"""

from app.models.anime import Anime
from app.models.episode import Episode
from app.models.favorite import Favorite
from app.models.password_reset_token import PasswordResetToken
from app.models.refresh_session import RefreshSession
from app.models.user import User
from app.models.watch_progress import WatchProgress

__all__ = [
    "Anime",
    "Episode",
    "Favorite",
    "PasswordResetToken",
    "RefreshSession",
    "User",
    "WatchProgress",
]
