from pathlib import Path

from app.integrations.video_source.provider import StreamInfo, VideoProvider


class LocalVideoProvider(VideoProvider):
    def __init__(self, directory: Path | str):
        self.directory = Path(directory).expanduser()

    def get_stream(self, external_episode_id: str) -> StreamInfo:
        raise NotImplementedError(
            "LocalVideoProvider requires a platform episode ID"
        )

    def get_stream_for_episode(
        self, external_episode_id: str, episode_id: str
    ) -> StreamInfo:
        return StreamInfo(
            stream_url=f"/api/watch/{episode_id}/content",
            provider="local",
        )

    def get_file_path(self, episode_id: str) -> Path | None:
        directory = self.directory.resolve()
        path = (directory / f"{episode_id}.mp4").resolve()

        if not path.is_relative_to(directory):
            return None

        return path if path.is_file() else None