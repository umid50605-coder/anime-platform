from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user, get_favorite_service
from app.models.user import User
from app.schemas.favorite import FavoriteCreate, FavoriteRead
from app.services.favorite import AnimeNotFoundError, FavoriteService

router = APIRouter()


@router.get("/", response_model=list[FavoriteRead])
def list_favorites(
    current_user: User = Depends(get_current_user),
    favorite_service: FavoriteService = Depends(get_favorite_service),
) -> list[FavoriteRead]:
    return favorite_service.list_for_user(current_user.id)


@router.post("/", response_model=FavoriteRead, status_code=status.HTTP_201_CREATED)
def add_favorite(
    data: FavoriteCreate,
    current_user: User = Depends(get_current_user),
    favorite_service: FavoriteService = Depends(get_favorite_service),
) -> FavoriteRead:
    try:
        return favorite_service.add(current_user.id, data.anime_id)
    except AnimeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/{anime_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(
    anime_id: str,
    current_user: User = Depends(get_current_user),
    favorite_service: FavoriteService = Depends(get_favorite_service),
) -> None:
    removed = favorite_service.remove(current_user.id, anime_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Favorite not found")
