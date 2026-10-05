from dataclasses import dataclass
from datetime import datetime

from app.integrations.video_source import StreamInfo, VideoProvider
from app.models.watch_progress import WatchProgress
from app.repositories.episode import EpisodeRepository
from app.repositories.watch import WatchRepository


class EpisodeNotFoundError(Exception):
    pass


@dataclass
class WatchHistoryItem:
    """
    Domain-level watch history entry - already carries `anime_id` (resolved
    via the episode, since WatchProgress itself only stores episode_id).
    Mirrors the AnimeDetailResult pattern in app/services/anime/service.py:
    the service returns a plain dataclass, and the API layer maps it onto
    the Pydantic response schema. Keeps this resolution (and the repository
    access it requires) out of the router - see PROJECT_RULES.md layering
    rules.
    """

    episode_id: str
    anime_id: str
    position_seconds: int
    updated_at: datetime


class WatchService:
    def __init__(
        self,
        watch_repository: WatchRepository,
        episode_repository: EpisodeRepository,
        video_provider: VideoProvider,
    ):
        self.watch_repository = watch_repository
        self.episode_repository = episode_repository
        self.video_provider = video_provider

    def get_progress(self, user_id: str, episode_id: str) -> WatchProgress | None:
        return self.watch_repository.get_progress(user_id, episode_id)

    def update_progress(
        self, user_id: str, episode_id: str, position_seconds: int
    ) -> WatchProgress:
        if position_seconds < 0:
            raise ValueError("position_seconds must not be negative")
        episode = self.episode_repository.get_by_id(episode_id)
        if episode is None:
            raise EpisodeNotFoundError(f"Episode {episode_id} not found")
        return self.watch_repository.upsert_progress(user_id, episode_id, position_seconds)

    def list_history(self, user_id: str, limit: int = 50) -> list[WatchHistoryItem]:
        """
        Assembles watch-history entries, including each row's anime_id -
        this is the response-shaping work that used to live in the router
        (reaching into watch_service.watch_repository directly, which
        violated the API -> Service -> Repository layering rule). The
        router now only needs to call this and serialize the result.
        """
        rows = self.watch_repository.list_history_for_user(user_id, limit=limit)
        return [
            WatchHistoryItem(
                episode_id=row.episode_id,
                anime_id=self.watch_repository.get_anime_id_for_episode(row.episode_id) or "",
                position_seconds=row.position_seconds,
                updated_at=row.updated_at,
            )
            for row in rows
        ]

    def get_stream(self, episode_id: str) -> StreamInfo:
        episode = self.episode_repository.get_by_id(episode_id)
        if episode is None:
            raise EpisodeNotFoundError(f"Episode {episode_id} not found")
        return self.video_provider.get_stream(episode.external_episode_id)
