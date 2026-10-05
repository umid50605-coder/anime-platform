from functools import lru_cache

from app.core.config import get_settings
from app.integrations.anime_api.logging_provider import LoggingAnimeProvider
from app.integrations.anime_api.mock_provider import MockAnimeProvider
from app.integrations.anime_api.provider import AnimeProvider


@lru_cache
def get_anime_provider() -> AnimeProvider:
    """
    Returns the configured AnimeProvider implementation, wrapped for
    provider-failure logging (see logging_provider.py - purely additive,
    does not change behavior or the AnimeProvider interface).

    Only "mock" exists today. Adding a real vendor later means: implement a
    new AnimeProvider subclass, add a branch here, done - no other file in
    the codebase needs to change.
    """
    settings = get_settings()
    if settings.anime_provider == "mock":
        return LoggingAnimeProvider(MockAnimeProvider())
    raise ValueError(f"Unknown anime_provider setting: {settings.anime_provider}")
