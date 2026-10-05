from dataclasses import dataclass

import pytest
from app.integrations.video_source.provider import StreamInfo, VideoProvider
from app.services.watch.service import EpisodeNotFoundError, WatchService


@dataclass
class FakeEpisode:
    id: str
    external_episode_id: str


@dataclass
class FakeProgress:
    user_id: str
    episode_id: str
    position_seconds: int
    updated_at: str = "2026-01-01T00:00:00Z"


class FakeEpisodeRepository:
    def __init__(self, episodes: dict[str, FakeEpisode]):
        self._episodes = episodes

    def get_by_id(self, episode_id: str) -> FakeEpisode | None:
        return self._episodes.get(episode_id)


class FakeWatchRepository:
    def __init__(self):
        self._progress: dict[tuple, FakeProgress] = {}
        self._episode_anime_map: dict[str, str] = {}

    def get_progress(self, user_id: str, episode_id: str) -> FakeProgress | None:
        return self._progress.get((user_id, episode_id))

    def upsert_progress(self, user_id: str, episode_id: str, position_seconds: int) -> FakeProgress:
        progress = FakeProgress(
            user_id=user_id, episode_id=episode_id, position_seconds=position_seconds
        )
        self._progress[(user_id, episode_id)] = progress
        return progress

    def list_history_for_user(self, user_id: str, limit: int = 50) -> list[FakeProgress]:
        rows = [p for (u, _), p in self._progress.items() if u == user_id]
        return rows[:limit]

    def get_anime_id_for_episode(self, episode_id: str) -> str | None:
        return self._episode_anime_map.get(episode_id)


class FakeVideoProvider(VideoProvider):
    def get_stream(self, external_episode_id: str) -> StreamInfo:
        return StreamInfo(stream_url=f"https://fake/{external_episode_id}.m3u8", provider="fake")


@pytest.fixture()
def watch_service():
    episodes = {"ep-1": FakeEpisode(id="ep-1", external_episode_id="ext-ep-1")}
    repository = FakeWatchRepository()
    repository._episode_anime_map["ep-1"] = "anime-1"
    return WatchService(
        watch_repository=repository,
        episode_repository=FakeEpisodeRepository(episodes),
        video_provider=FakeVideoProvider(),
    )


def test_update_progress_creates_then_overwrites(watch_service):
    first = watch_service.update_progress("user-1", "ep-1", 100)
    assert first.position_seconds == 100

    second = watch_service.update_progress("user-1", "ep-1", 923)
    assert second.position_seconds == 923
    # upsert, not a second row: fetching again returns the latest value
    assert watch_service.get_progress("user-1", "ep-1").position_seconds == 923


def test_update_progress_rejects_negative_position(watch_service):
    with pytest.raises(ValueError):
        watch_service.update_progress("user-1", "ep-1", -5)


def test_update_progress_unknown_episode_raises(watch_service):
    with pytest.raises(EpisodeNotFoundError):
        watch_service.update_progress("user-1", "does-not-exist", 10)


def test_get_stream_resolves_via_provider(watch_service):
    stream = watch_service.get_stream("ep-1")
    assert stream.stream_url == "https://fake/ext-ep-1.m3u8"


def test_get_stream_unknown_episode_raises(watch_service):
    with pytest.raises(EpisodeNotFoundError):
        watch_service.get_stream("does-not-exist")


def test_list_history_resolves_anime_id_via_episode(watch_service):
    """
    Regression test for the API -> Service -> Repository layering fix:
    this assembly (episode_id + resolved anime_id + position/updated_at)
    used to happen in the router by reaching into
    `watch_service.watch_repository` directly. It now happens inside
    WatchService.list_history() itself.
    """
    watch_service.update_progress("user-1", "ep-1", 923)

    history = watch_service.list_history("user-1")

    assert len(history) == 1
    entry = history[0]
    assert entry.episode_id == "ep-1"
    assert entry.anime_id == "anime-1"
    assert entry.position_seconds == 923


def test_list_history_uses_empty_anime_id_when_episode_unresolvable(watch_service):
    """Preserves the existing fallback (empty string, not an error) for an
    orphaned history row - see app/services/watch/service.py."""
    watch_service.watch_repository.upsert_progress("user-1", "unmapped-episode", 10)

    history = watch_service.list_history("user-1")

    assert len(history) == 1
    assert history[0].anime_id == ""


def test_list_history_only_returns_requesting_users_rows(watch_service):
    watch_service.update_progress("user-1", "ep-1", 10)
    watch_service.watch_repository.upsert_progress("user-2", "ep-1", 20)

    history = watch_service.list_history("user-1")

    assert len(history) == 1
    assert history[0].position_seconds == 10
