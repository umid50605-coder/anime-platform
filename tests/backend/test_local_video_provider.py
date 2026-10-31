from app.integrations.video_source.local_provider import LocalVideoProvider


def test_get_file_path_returns_existing_video(tmp_path):
    episode_id = "episode-123"
    video_file = tmp_path / f"{episode_id}.mp4"
    video_file.write_bytes(b"video")

    provider = LocalVideoProvider(tmp_path)

    assert provider.get_file_path(episode_id) == video_file


def test_get_file_path_returns_none_when_file_missing(tmp_path):
    provider = LocalVideoProvider(tmp_path)

    assert provider.get_file_path("missing-episode") is None


def test_get_file_path_blocks_path_traversal(tmp_path):
    video_directory = tmp_path / "videos"
    video_directory.mkdir()

    outside_file = tmp_path / "outside.mp4"
    outside_file.write_bytes(b"not allowed")

    provider = LocalVideoProvider(video_directory)

    assert provider.get_file_path("../outside") is None


def test_get_stream_for_episode_returns_content_endpoint(tmp_path):
    provider = LocalVideoProvider(tmp_path)

    stream = provider.get_stream_for_episode(
        "external-123",
        "episode-123",
    )

    assert stream.stream_url == "/api/watch/episode-123/content"
    assert stream.provider == "local"
