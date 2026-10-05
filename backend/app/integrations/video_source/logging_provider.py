"""
LoggingVideoProvider: a transparent logging decorator for VideoProvider.

Same rationale as LoggingAnimeProvider (see app/integrations/anime_api/
logging_provider.py) - logs provider failures with safe context and
re-raises unchanged; never logs stream URLs, tokens, or credentials.
"""

from app.core.logging import get_logger
from app.integrations.video_source.provider import StreamInfo, VideoProvider

logger = get_logger(__name__)


class LoggingVideoProvider(VideoProvider):
    def __init__(self, delegate: VideoProvider):
        self._delegate = delegate

    def get_stream(self, external_episode_id: str) -> StreamInfo:
        try:
            return self._delegate.get_stream(external_episode_id)
        except Exception:
            logger.error(
                "video provider failure operation=get_stream external_episode_id=%s",
                external_episode_id,
            )
            raise
