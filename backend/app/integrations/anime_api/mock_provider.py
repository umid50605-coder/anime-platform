"""
MockAnimeProvider: an in-memory stand-in for a real anime-metadata vendor.

This exists ONLY to prove the AnimeProvider abstraction works end-to-end
(service -> provider -> data), per the instruction to not implement a real
external vendor integration yet. Swapping this for e.g. an AniList adapter
later should require no changes to AnimeService or anything above it.
"""

from app.integrations.anime_api.provider import AnimeMetadata, AnimeProvider, EpisodeMetadata

_FIXTURE_ANIME: dict[str, AnimeMetadata] = {
    "mock-1": AnimeMetadata(
        external_id="mock-1",
        title="Skybound Chronicles",
        slug="skybound-chronicles",
        poster_url="https://placehold.co/300x450?text=Skybound+Chronicles",
        synopsis=(
            "A placeholder synopsis for a placeholder anime, used only for foundation testing."
        ),
        genres=["Adventure", "Fantasy"],
    ),
    "mock-2": AnimeMetadata(
        external_id="mock-2",
        title="Neon Ronin",
        slug="neon-ronin",
        poster_url="https://placehold.co/300x450?text=Neon+Ronin",
        synopsis="Another placeholder synopsis, used only for foundation testing.",
        genres=["Action", "Sci-Fi"],
    ),
}

_FIXTURE_EPISODES: dict[str, list[EpisodeMetadata]] = {
    "mock-1": [
        EpisodeMetadata(external_episode_id="mock-1-ep-1", episode_number=1, title="Departure"),
        EpisodeMetadata(external_episode_id="mock-1-ep-2", episode_number=2, title="The Storm"),
    ],
    "mock-2": [
        EpisodeMetadata(external_episode_id="mock-2-ep-1", episode_number=1, title="Neon Alley"),
    ],
}


class MockAnimeProvider(AnimeProvider):
    name = "mock"

    def get_anime(self, external_id: str) -> AnimeMetadata:
        try:
            return _FIXTURE_ANIME[external_id]
        except KeyError as exc:
            raise ValueError(f"Unknown mock anime id: {external_id}") from exc

    def search_anime(self, query: str) -> list[AnimeMetadata]:
        query_lower = query.lower().strip()
        if not query_lower:
            return list(_FIXTURE_ANIME.values())
        return [a for a in _FIXTURE_ANIME.values() if query_lower in a.title.lower()]

    def list_episodes(self, external_id: str) -> list[EpisodeMetadata]:
        return _FIXTURE_EPISODES.get(external_id, [])
