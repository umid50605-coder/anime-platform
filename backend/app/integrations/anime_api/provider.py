"""
AnimeProvider: the abstraction boundary between our application and any
external anime-metadata vendor (AniList, Jikan/MyAnimeList, Kitsu, ...).

Nothing outside app/integrations/anime_api may import a vendor SDK/HTTP
client directly. Services depend on this interface, not on a concrete
provider, so the vendor can be swapped by adding a new class here and
changing one line in the provider factory (see factory.py).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class AnimeMetadata:
    """Vendor-agnostic representation of one anime, as returned by a provider."""

    external_id: str
    title: str
    slug: str
    poster_url: str = ""
    synopsis: str = ""
    genres: list[str] = field(default_factory=list)
    alternative_titles: list[str] = field(default_factory=list)
    cover_url: str = ""
    release_year: int | None = None
    status: str | None = None


@dataclass
class EpisodeMetadata:
    """Vendor-agnostic representation of one episode, as returned by a provider."""

    external_episode_id: str
    episode_number: int
    title: str = ""


class AnimeProvider(ABC):
    """Interface every anime-metadata integration must implement."""

    #: Short machine name identifying this provider (e.g. "mock", "anilist").
    #: Stored alongside external_id in our DB so an id remains unambiguous
    #: even if we support multiple providers side by side later.
    name: str = "unknown"

    def list_anime(self, page: int = 1, limit: int = 25) -> list[AnimeMetadata]:
        """Return a page of provider anime records.

        Providers that do not expose a catalog may keep the default empty
        implementation; search and detail remain the required operations.
        """
        return []

    @abstractmethod
    def get_anime(self, external_id: str) -> AnimeMetadata:
        """Fetch metadata for a single anime by its provider-specific id."""

    @abstractmethod
    def search_anime(self, query: str) -> list[AnimeMetadata]:
        """Search the provider's catalog by free-text query."""

    @abstractmethod
    def list_episodes(self, external_id: str) -> list[EpisodeMetadata]:
        """List episodes for an anime by its provider-specific id."""
