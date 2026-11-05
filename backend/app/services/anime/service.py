from dataclasses import dataclass

from app.integrations.anime_api import AnimeMetadata, AnimeProvider
from app.models.anime import Anime
from app.repositories.anime import AnimeRepository


@dataclass
class AnimeDetailResult:
    """Domain-level combination of our DB record + live provider metadata."""

    anime: Anime
    synopsis: str
    genres: list[str]


class AnimeService:
    def __init__(self, anime_repository: AnimeRepository, anime_provider: AnimeProvider):
        self.anime_repository = anime_repository
        self.anime_provider = anime_provider

    def list_catalog(self, *, offset: int = 0, limit: int = 100) -> list[Anime]:
        """Returns the platform's published catalog (our own DB, not the provider)."""
        return self.anime_repository.list_all(offset=offset, limit=limit)

    def search_catalog(self, query: str) -> list[Anime]:
        return self.anime_repository.search(query)

    def get_by_slug(self, slug: str) -> Anime | None:
        return self.anime_repository.get_by_slug(slug)

    def get_detail(self, slug: str) -> AnimeDetailResult | None:
        """
        Detail view = our cached record (title/poster/slug) + fields fetched
        live from the provider (synopsis/genres) that we deliberately do not
        store locally.
        """
        anime = self.anime_repository.get_by_slug(slug)
        if anime is None:
            return None
        metadata = self.anime_provider.get_anime(anime.external_id)
        return AnimeDetailResult(anime=anime, synopsis=metadata.synopsis, genres=metadata.genres)

    def search(self, query: str) -> list[AnimeMetadata]:
        """
        Search is answered live from the provider, not from our DB - we do
        not maintain a full searchable mirror of the external catalog.
        """
        return self.anime_provider.search_anime(query)

    def import_from_provider(self, external_id: str) -> Anime:
        """
        Ensures a local Anime mapping row exists for a given provider id,
        creating it from provider metadata if needed. This is how an anime
        gets "published" into our own catalog.
        """
        provider_name = self.anime_provider.name
        existing = self.anime_repository.get_by_external_id(provider_name, external_id)
        if existing:
            self.anime_repository.add_external_mapping(existing.id, provider_name, external_id)
            self.anime_repository.db.commit()
            return existing

        metadata = self.anime_provider.get_anime(external_id)
        anime = Anime(
            external_provider=provider_name,
            external_id=metadata.external_id,
            slug=metadata.slug,
            title=metadata.title,
            poster_url=metadata.poster_url,
        )
        return self.anime_repository.create_with_external_mapping(
            anime, provider_name, metadata.external_id
        )
