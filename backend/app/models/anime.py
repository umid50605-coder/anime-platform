import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Anime(Base):
    """
    Platform-side anime record.

    IMPORTANT: this is a *mapping* to an external metadata provider, not a
    mirror of it. Only the minimal fields needed to render a catalog/detail
    page without an external call on every request are cached here
    (title/slug/poster). Anything else (genres, full synopsis, ratings,
    related titles, etc.) is fetched live through AnimeProvider when needed.
    """

    __tablename__ = "anime"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)

    # Which provider this external_id belongs to, e.g. "mock" today, maybe
    # "anilist" or "jikan" later. Lets the same internal id survive a
    # provider swap/migration.
    external_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    external_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    slug: Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    poster_url: Mapped[str] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
