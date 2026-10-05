from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WatchProgressUpdate(BaseModel):
    position_seconds: int = Field(ge=0)


class WatchProgressRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    episode_id: str
    position_seconds: int
    updated_at: datetime


class WatchHistoryEntry(BaseModel):
    """A watch-history row - this is WatchProgress data viewed through a
    different lens (see app/models/watch_progress.py for the rationale)."""

    episode_id: str
    anime_id: str
    position_seconds: int
    updated_at: datetime
