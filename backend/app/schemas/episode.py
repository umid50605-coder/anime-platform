from pydantic import BaseModel, ConfigDict


class EpisodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    anime_id: str
    episode_number: int
    title: str | None = None


class StreamInfo(BaseModel):
    """Returned by the watch endpoint - sourced live from VideoProvider."""

    stream_url: str
    provider: str
