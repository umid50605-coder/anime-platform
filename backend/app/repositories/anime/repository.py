from sqlalchemy.orm import Session

from app.models.anime import Anime


class AnimeRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, anime_id: str) -> Anime | None:
        return self.db.get(Anime, anime_id)

    def get_by_slug(self, slug: str) -> Anime | None:
        return self.db.query(Anime).filter(Anime.slug == slug).first()

    def get_by_external_id(self, provider: str, external_id: str) -> Anime | None:
        return (
            self.db.query(Anime)
            .filter(Anime.external_provider == provider, Anime.external_id == external_id)
            .first()
        )

    def list_all(self) -> list[Anime]:
        return self.db.query(Anime).order_by(Anime.title).all()

    def create(self, anime: Anime) -> Anime:
        self.db.add(anime)
        self.db.commit()
        self.db.refresh(anime)
        return anime
