"""
LoggingAnimeProvider: a transparent logging decorator for AnimeProvider.

Wraps any concrete AnimeProvider (MockAnimeProvider today, a real vendor
adapter later) without changing its behavior: every call is delegated as-is,
and any exception is logged with safe, non-secret context (provider name,
operation, the external id/anime being requested) then re-raised exactly as
raised. Callers - AnimeService, tests - see identical behavior with or
without this wrapper.

Deliberately never logs: API keys, Authorization headers, or the raw
external response body - none of that is available at this layer anyway,
but a real provider adapter added later should keep it that way.
"""

from app.core.logging import get_logger
from app.integrations.anime_api.provider import AnimeMetadata, AnimeProvider, EpisodeMetadata

logger = get_logger(__name__)


class LoggingAnimeProvider(AnimeProvider):
    def __init__(self, delegate: AnimeProvider):
        self._delegate = delegate
        self.name = delegate.name

    def get_anime(self, external_id: str) -> AnimeMetadata:
        try:
            return self._delegate.get_anime(external_id)
        except Exception:
            logger.error(
                "anime provider failure provider=%s operation=get_anime external_id=%s",
                self.name,
                external_id,
            )
            raise

    def search_anime(self, query: str) -> list[AnimeMetadata]:
        try:
            return self._delegate.search_anime(query)
        except Exception:
            # The query text itself is user-supplied free text - not logged.
            logger.error(
                "anime provider failure provider=%s operation=search_anime",
                self.name,
            )
            raise

    def list_episodes(self, external_id: str) -> list[EpisodeMetadata]:
        try:
            return self._delegate.list_episodes(external_id)
        except Exception:
            logger.error(
                "anime provider failure provider=%s operation=list_episodes external_id=%s",
                self.name,
                external_id,
            )
            raise
