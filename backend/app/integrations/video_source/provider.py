"""
VideoProvider: the abstraction boundary between our application and any
external video-streaming vendor.

Only a basic "give me a playable URL for this episode" contract is defined
for this foundation. Adaptive bitrate, bandwidth estimation, prefetching etc.
are explicitly out of scope until a real, measured need exists - adding them
later means adding methods/fields here, not restructuring callers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class StreamInfo:
    """Vendor-agnostic representation of a playable stream."""

    stream_url: str
    provider: str


class VideoProvider(ABC):
    """Interface every video-streaming integration must implement."""

    @abstractmethod
    def get_stream(self, external_episode_id: str) -> StreamInfo:
        """Resolve a playable stream URL for an episode's provider-specific id."""

    def get_stream_for_episode(
        self, external_episode_id: str, episode_id: str
    ) -> StreamInfo:
        """Resolve a stream using provider ID and platform episode ID."""
        return self.get_stream(external_episode_id)

    def get_file_path(self, episode_id: str) -> Path | None:
        """Return a local video path, or None for URL-based providers."""
        return None
