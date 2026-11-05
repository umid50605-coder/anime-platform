from functools import lru_cache

from app.core.config import get_settings
from app.integrations.anime_api.jikan_provider import get_jikan_provider
from app.integrations.anime_api.logging_provider import LoggingAnimeProvider
from app.integrations.anime_api.mock_provider import MockAnimeProvider
from app.integrations.anime_api.provider import AnimeProvider


@lru_cache
def get_anime_provider() -> AnimeProvider:
    """
    Returns the configured AnimeProvider implementation, wrapped for
    provider-failure logging (see logging_provider.py - purely additive,
    does not change behavior or the AnimeProvider interface).

    Supported providers are "mock" and "jikan". Adding another vendor means:
    implement an AnimeProvider subclass, add a branch here, and leave the rest
    of the application unchanged.
    """
    settings = get_settings()
    if settings.anime_provider == "mock":
        return LoggingAnimeProvider(MockAnimeProvider())
    if settings.anime_provider == "jikan":
        return LoggingAnimeProvider(get_jikan_provider())
    raise ValueError(f"Unknown anime_provider setting: {settings.anime_provider}")
