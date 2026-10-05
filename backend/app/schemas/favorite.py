from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FavoriteCreate(BaseModel):
    anime_id: str


class FavoriteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    anime_id: str
    created_at: datetime
