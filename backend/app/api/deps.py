"""
FastAPI dependency wiring.

Route handlers depend on *services* (never repositories or providers
directly). This module is where a Session becomes a Repository becomes a
Service - the composition root for the API layer.
"""

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_access_token_claims
from app.integrations.anime_api import AnimeProvider, get_anime_provider
from app.integrations.video_source import VideoProvider, get_video_provider
from app.models.user import User
from app.repositories.anime import AnimeRepository
from app.repositories.episode import EpisodeRepository
from app.repositories.favorite import FavoriteRepository
from app.repositories.refresh_session import RefreshSessionRepository
from app.repositories.user import UserRepository
from app.repositories.watch import WatchRepository
from app.services.anime import AnimeService
from app.services.auth import AuthService
from app.services.episode import EpisodeService
from app.services.favorite import FavoriteService
from app.services.user import UserService
from app.services.watch import WatchService

# --- Repositories -----------------------------------------------------------


def get_user_repository(db: Session = Depends(get_db)) -> UserRepository:
    return UserRepository(db)


def get_anime_repository(db: Session = Depends(get_db)) -> AnimeRepository:
    return AnimeRepository(db)


def get_episode_repository(db: Session = Depends(get_db)) -> EpisodeRepository:
    return EpisodeRepository(db)


def get_watch_repository(db: Session = Depends(get_db)) -> WatchRepository:
    return WatchRepository(db)


def get_favorite_repository(db: Session = Depends(get_db)) -> FavoriteRepository:
    return FavoriteRepository(db)


def get_refresh_session_repository(
    db: Session = Depends(get_db),
) -> RefreshSessionRepository:
    return RefreshSessionRepository(db)


# --- Providers ----------------------------------------------------------------


def get_anime_provider_dep() -> AnimeProvider:
    return get_anime_provider()


def get_video_provider_dep() -> VideoProvider:
    return get_video_provider()


# --- Services -----------------------------------------------------------------


def get_user_service(user_repository: UserRepository = Depends(get_user_repository)) -> UserService:
    return UserService(user_repository)


def get_auth_service(
    user_service: UserService = Depends(get_user_service),
    refresh_session_repository: RefreshSessionRepository = Depends(get_refresh_session_repository),
) -> AuthService:
    return AuthService(user_service, refresh_session_repository)


def get_anime_service(
    anime_repository: AnimeRepository = Depends(get_anime_repository),
    anime_provider: AnimeProvider = Depends(get_anime_provider_dep),
) -> AnimeService:
    return AnimeService(anime_repository, anime_provider)


def get_episode_service(
    episode_repository: EpisodeRepository = Depends(get_episode_repository),
    anime_repository: AnimeRepository = Depends(get_anime_repository),
    anime_provider: AnimeProvider = Depends(get_anime_provider_dep),
) -> EpisodeService:
    return EpisodeService(episode_repository, anime_repository, anime_provider)


def get_watch_service(
    watch_repository: WatchRepository = Depends(get_watch_repository),
    episode_repository: EpisodeRepository = Depends(get_episode_repository),
    video_provider: VideoProvider = Depends(get_video_provider_dep),
) -> WatchService:
    return WatchService(watch_repository, episode_repository, video_provider)


def get_favorite_service(
    favorite_repository: FavoriteRepository = Depends(get_favorite_repository),
    anime_repository: AnimeRepository = Depends(get_anime_repository),
) -> FavoriteService:
    return FavoriteService(favorite_repository, anime_repository)


# --- Current user -------------------------------------------------------------


def get_current_user(
    token_claims: dict[str, object] = Depends(get_current_access_token_claims),
    user_service: UserService = Depends(get_user_service),
    refresh_session_repository: RefreshSessionRepository = Depends(get_refresh_session_repository),
) -> User:
    user_id = token_claims.get("sub")
    family_id = token_claims.get("sid")
    if (
        not isinstance(user_id, str)
        or not isinstance(family_id, str)
        or not family_id
        or not refresh_session_repository.has_active_family(user_id, family_id)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = user_service.get_by_id(user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
