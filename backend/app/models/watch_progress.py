import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(UTC)


class WatchProgress(Base):
    """
    Resume position for a user watching an episode.

    Design note: "watch history" is intentionally NOT a separate table for
    this foundation. A user's watch history is simply their WatchProgress
    rows ordered by `updated_at` descending. This avoids keeping two copies
    of overlapping state in sync. If a real need for a distinct event log
    (e.g. "watched this twice on two different days") shows up later, a
    dedicated append-only history table can be added without touching this
    one - see ARCHITECTURE.md.
    """

    __tablename__ = "watch_progress"
    __table_args__ = (UniqueConstraint("user_id", "episode_id", name="uq_user_episode_progress"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    episode_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("episodes.id"), nullable=False, index=True
    )

    position_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
