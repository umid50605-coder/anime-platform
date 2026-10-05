"""
MockVideoProvider: a stand-in for a real video-streaming vendor.

Returns a deterministic placeholder URL so the watch flow (episode -> stream
URL) can be exercised end-to-end without a real external dependency or any
copyrighted/licensed content.
"""

from app.integrations.video_source.provider import StreamInfo, VideoProvider


class MockVideoProvider(VideoProvider):
    def get_stream(self, external_episode_id: str) -> StreamInfo:
        return StreamInfo(
            stream_url=f"https://example-cdn.test/streams/{external_episode_id}.m3u8",
            provider="mock",
        )
