from sqlalchemy.orm import Session

from app.models.episode import Episode


class EpisodeRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, episode_id: str) -> Episode | None:
        return self.db.get(Episode, episode_id)

    def get_by_external_id(self, anime_id: str, external_episode_id: str) -> Episode | None:
        return (
            self.db.query(Episode)
            .filter(
                Episode.anime_id == anime_id,
                Episode.external_episode_id == external_episode_id,
            )
            .first()
        )

    def list_for_anime(self, anime_id: str) -> list[Episode]:
        return (
            self.db.query(Episode)
            .filter(Episode.anime_id == anime_id)
            .order_by(Episode.episode_number)
            .all()
        )

    def create(self, episode: Episode) -> Episode:
        self.db.add(episode)
        self.db.commit()
        self.db.refresh(episode)
        return episode
