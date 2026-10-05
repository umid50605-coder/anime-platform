from fastapi import APIRouter

from app.api.anime.router import router as anime_router
from app.api.auth.router import router as auth_router
from app.api.episodes.router import router as episodes_router
from app.api.favorites.router import router as favorites_router
from app.api.search.router import router as search_router
from app.api.users.router import router as users_router
from app.api.watch.router import router as watch_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(anime_router, prefix="/anime", tags=["anime"])
api_router.include_router(episodes_router, prefix="/episodes", tags=["episodes"])
api_router.include_router(search_router, prefix="/search", tags=["search"])
api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(watch_router, prefix="/watch", tags=["watch"])
api_router.include_router(favorites_router, prefix="/favorites", tags=["favorites"])
