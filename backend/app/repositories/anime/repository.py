from sqlalchemy.orm import Session

from app.models.anime import Anime
from app.models.anime_external_id import AnimeExternalId


class AnimeRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, anime_id: str) -> Anime | None:
        return self.db.get(Anime, anime_id)

    def get_by_slug(self, slug: str) -> Anime | None:
        return self.db.query(Anime).filter(Anime.slug == slug).first()

    def get_by_external_id(self, provider: str, external_id: str) -> Anime | None:
        legacy = (
            self.db.query(Anime)
            .filter(Anime.external_provider == provider, Anime.external_id == external_id)
            .first()
        )
        if legacy is not None:
            return legacy
        mapping = (
            self.db.query(AnimeExternalId)
            .filter(
                AnimeExternalId.provider == provider,
                AnimeExternalId.external_id == external_id,
            )
            .first()
        )
        return self.get_by_id(mapping.anime_id) if mapping else None

    def list_all(self, *, offset: int = 0, limit: int = 100) -> list[Anime]:
        return (
            self.db.query(Anime)
            .order_by(Anime.title)
            .offset(offset)
            .limit(limit)
            .all()
        )

    def search(self, query: str, *, offset: int = 0, limit: int = 100) -> list[Anime]:
        return (
            self.db.query(Anime)
            .filter(Anime.title.ilike(f"%{query}%"))
            .order_by(Anime.title)
            .offset(offset)
            .limit(limit)
            .all()
        )

    def add_external_mapping(
        self, anime_id: str, provider: str, external_id: str
    ) -> AnimeExternalId:
        existing = (
            self.db.query(AnimeExternalId)
            .filter(
                AnimeExternalId.provider == provider,
                AnimeExternalId.external_id == external_id,
            )
            .first()
        )
        if existing:
            return existing
        mapping = AnimeExternalId(
            anime_id=anime_id, provider=provider, external_id=external_id
        )
        self.db.add(mapping)
        self.db.flush()
        return mapping

    def create(self, anime: Anime) -> Anime:
        self.db.add(anime)
        self.db.flush()
        self.db.commit()
        self.db.refresh(anime)
        return anime

    def create_with_external_mapping(
        self, anime: Anime, provider: str, external_id: str
    ) -> Anime:
        self.db.add(anime)
        self.db.flush()
        self.add_external_mapping(anime.id, provider, external_id)
        self.db.commit()
        self.db.refresh(anime)
        return anime
