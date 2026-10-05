from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_episode_service
from app.schemas.episode import EpisodeRead
from app.services.episode import EpisodeService

router = APIRouter()


@router.get("/anime/{anime_id}", response_model=list[EpisodeRead])
def list_episodes_for_anime(
    anime_id: str, episode_service: EpisodeService = Depends(get_episode_service)
) -> list[EpisodeRead]:
    return episode_service.list_for_anime(anime_id)


@router.get("/{episode_id}", response_model=EpisodeRead)
def get_episode(
    episode_id: str, episode_service: EpisodeService = Depends(get_episode_service)
) -> EpisodeRead:
    episode = episode_service.get_by_id(episode_id)
    if episode is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Episode not found")
    return episode
