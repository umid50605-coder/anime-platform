import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Episode(Base):
    """
    Platform-side episode record for one Anime.

    Like Anime, this is a mapping/cache - `external_episode_id` is the key
    used to ask VideoProvider for a stream, and (optionally) AnimeProvider
    for episode-level metadata (title/synopsis) not cached here.
    """

    __tablename__ = "episodes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    anime_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("anime.id"), nullable=False, index=True
    )

    external_episode_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    episode_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
