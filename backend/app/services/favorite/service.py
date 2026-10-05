from app.models.favorite import Favorite
from app.repositories.anime import AnimeRepository
from app.repositories.favorite import FavoriteRepository


class AnimeNotFoundError(Exception):
    pass


class FavoriteService:
    def __init__(self, favorite_repository: FavoriteRepository, anime_repository: AnimeRepository):
        self.favorite_repository = favorite_repository
        self.anime_repository = anime_repository

    def add(self, user_id: str, anime_id: str) -> Favorite:
        if self.anime_repository.get_by_id(anime_id) is None:
            raise AnimeNotFoundError(f"Anime {anime_id} not found")
        return self.favorite_repository.add(user_id, anime_id)

    def remove(self, user_id: str, anime_id: str) -> bool:
        return self.favorite_repository.remove(user_id, anime_id)

    def list_for_user(self, user_id: str) -> list[Favorite]:
        return self.favorite_repository.list_for_user(user_id)
