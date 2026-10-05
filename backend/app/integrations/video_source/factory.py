from functools import lru_cache

from app.core.config import get_settings
from app.integrations.video_source.logging_provider import LoggingVideoProvider
from app.integrations.video_source.mock_provider import MockVideoProvider
from app.integrations.video_source.provider import VideoProvider


@lru_cache
def get_video_provider() -> VideoProvider:
    """
    Returns the configured VideoProvider implementation (only "mock" today),
    wrapped for provider-failure logging - see logging_provider.py.
    """
    settings = get_settings()
    if settings.video_provider == "mock":
        return LoggingVideoProvider(MockVideoProvider())
    raise ValueError(f"Unknown video_provider setting: {settings.video_provider}")
