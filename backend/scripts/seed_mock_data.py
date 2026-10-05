"""
Dev-only helper: seeds the local database with the two mock anime (and their
episodes) from MockAnimeProvider, so GET /api/anime/ etc. return something
without needing an admin panel (out of scope for this phase).

Usage (from backend/, with the venv active):
    PYTHONPATH=. python scripts/seed_mock_data.py
"""

from app.core.database import SessionLocal
from app.integrations.anime_api import get_anime_provider
from app.repositories.anime import AnimeRepository
from app.repositories.episode import EpisodeRepository
from app.services.anime import AnimeService
from app.services.episode import EpisodeService


def main() -> None:
    db = SessionLocal()
    try:
        anime_provider = get_anime_provider()
        anime_service = AnimeService(AnimeRepository(db), anime_provider)
        episode_service = EpisodeService(EpisodeRepository(db), AnimeRepository(db), anime_provider)

        for external_id in ("mock-1", "mock-2"):
            anime = anime_service.import_from_provider(external_id)
            episodes = episode_service.import_episodes_from_provider(anime.id)
            print(f"Seeded '{anime.title}' ({anime.slug}) with {len(episodes)} episode(s)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
