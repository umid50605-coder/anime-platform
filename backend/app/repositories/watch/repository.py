from sqlalchemy.orm import Session

from app.models.episode import Episode
from app.models.watch_progress import WatchProgress


class WatchRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_progress(self, user_id: str, episode_id: str) -> WatchProgress | None:
        return (
            self.db.query(WatchProgress)
            .filter(WatchProgress.user_id == user_id, WatchProgress.episode_id == episode_id)
            .first()
        )

    def upsert_progress(
        self, user_id: str, episode_id: str, position_seconds: int
    ) -> WatchProgress:
        progress = self.get_progress(user_id, episode_id)
        if progress is None:
            progress = WatchProgress(
                user_id=user_id, episode_id=episode_id, position_seconds=position_seconds
            )
            self.db.add(progress)
        else:
            progress.position_seconds = position_seconds
        self.db.commit()
        self.db.refresh(progress)
        return progress

    def list_history_for_user(self, user_id: str, limit: int = 50) -> list[WatchProgress]:
        """
        Watch history = watch_progress rows ordered by most recently updated.
        See app/models/watch_progress.py for why this isn't a separate table.
        """
        return (
            self.db.query(WatchProgress)
            .filter(WatchProgress.user_id == user_id)
            .order_by(WatchProgress.updated_at.desc())
            .limit(limit)
            .all()
        )

    def get_anime_id_for_episode(self, episode_id: str) -> str | None:
        episode = self.db.get(Episode, episode_id)
        return episode.anime_id if episode else None
