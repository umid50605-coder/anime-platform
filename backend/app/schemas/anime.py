from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AnimeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    title: str
    poster_url: str | None = None
    created_at: datetime


class AnimeDetail(AnimeRead):
    """
    Detail view - adds fields sourced live from AnimeProvider (not stored in
    our own DB). `synopsis`/`genres` are provider-sourced, not persisted.
    """

    synopsis: str | None = None
    genres: list[str] = []


class AnimeSearchResult(BaseModel):
    """
    Search results come straight from AnimeProvider and are NOT persisted -
    this schema mirrors AnimeMetadata (see app/integrations/anime_api) rather
    than reusing the DB-backed AnimeRead schema.
    """

    external_id: str
    title: str
    slug: str
    poster_url: str = ""
    synopsis: str = ""
    genres: list[str] = []
