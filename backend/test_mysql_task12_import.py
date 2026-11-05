"""Manual MySQL verification for Task 12 import idempotency.

Run from ``backend`` after Alembic is at head:
    PYTHONPATH=. ./.venv/bin/python test_mysql_task12_import.py

The script creates uniquely named mock-provider rows, verifies repeated anime
and episode imports, then removes only the rows it created.
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.integrations.anime_api.provider import AnimeMetadata, AnimeProvider, EpisodeMetadata
from app.models.anime import Anime
from app.models.anime_external_id import AnimeExternalId
from app.models.episode import Episode
from app.repositories.anime import AnimeRepository
from app.repositories.episode import EpisodeRepository
from app.services.anime import AnimeService
from app.services.episode import EpisodeService


class Task12VerificationProvider(AnimeProvider):
    name = "task12-verification"

    def __init__(self, external_id: str) -> None:
        self.external_id = external_id

    def get_anime(self, external_id: str) -> AnimeMetadata:
        if external_id != self.external_id:
            raise ValueError("unexpected external id")
        return AnimeMetadata(
            external_id=external_id,
            title=f"Task 12 verification {external_id}",
            slug=f"task-12-verification-{external_id}",
            poster_url="",
            synopsis="",
            genres=[],
        )

    def search_anime(self, query: str) -> list[AnimeMetadata]:
        return []

    def list_episodes(self, external_id: str) -> list[EpisodeMetadata]:
        if external_id != self.external_id:
            raise ValueError("unexpected external id")
        return [
            EpisodeMetadata(f"{external_id}-episode-1", 1, "Episode one"),
            EpisodeMetadata(f"{external_id}-episode-2", 2, "Episode two"),
        ]


def main() -> None:
    settings = get_settings()
    if not settings.database_url.startswith("mysql+"):
        raise RuntimeError("DATABASE_URL must select MySQL for this verification")

    external_id = f"task12-{uuid4()}"
    provider = Task12VerificationProvider(external_id)
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    session = sessionmaker(bind=engine)()
    anime_id: str | None = None

    try:
        anime_repository = AnimeRepository(session)
        episode_repository = EpisodeRepository(session)
        anime_service = AnimeService(anime_repository, provider)
        episode_service = EpisodeService(episode_repository, anime_repository, provider)

        first_anime = anime_service.import_from_provider(external_id)
        second_anime = anime_service.import_from_provider(external_id)
        assert first_anime.id == second_anime.id, "repeated anime import changed internal ID"
        anime_id = first_anime.id

        anime_count = session.scalar(
            select(func.count()).select_from(Anime).where(Anime.id == anime_id)
        )
        mapping_count = session.scalar(
            select(func.count())
            .select_from(AnimeExternalId)
            .where(
                AnimeExternalId.provider == provider.name,
                AnimeExternalId.external_id == external_id,
            )
        )
        assert anime_count == 1, f"expected one anime row, got {anime_count}"
        assert mapping_count == 1, f"expected one external-ID mapping, got {mapping_count}"

        first_episodes = episode_service.import_episodes_from_provider(anime_id)
        second_episodes = episode_service.import_episodes_from_provider(anime_id)
        assert [episode.id for episode in first_episodes] == [
            episode.id for episode in second_episodes
        ], "repeated episode import changed internal IDs"

        episode_count = session.scalar(
            select(func.count()).select_from(Episode).where(Episode.anime_id == anime_id)
        )
        assert episode_count == 2, f"expected two episode rows, got {episode_count}"
        print("Task 12 MySQL import verification passed: anime=1, mapping=1, episodes=2")
    finally:
        if anime_id is not None:
            session.query(Episode).filter(Episode.anime_id == anime_id).delete()
            session.query(AnimeExternalId).filter(AnimeExternalId.anime_id == anime_id).delete()
            session.query(Anime).filter(Anime.id == anime_id).delete()
            session.commit()
        session.close()
        engine.dispose()


if __name__ == "__main__":
    main()
