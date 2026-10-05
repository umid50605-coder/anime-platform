from sqlalchemy.orm import Session

from app.models.favorite import Favorite


class FavoriteRepository:
    """
    NOTE ON SCOPE: the original repositories/ list (user, anime, episode,
    watch) did not include a "favorite" repository, even though
    api/favorites and services/favorite exist. A favorite is persisted
    state, so it needs a data-access layer like everything else - this
    class fills that gap. See ARCHITECTURE.md "Deviations from the
    requested structure" for the full explanation.
    """

    def __init__(self, db: Session):
        self.db = db

    def get(self, user_id: str, anime_id: str) -> Favorite | None:
        return (
            self.db.query(Favorite)
            .filter(Favorite.user_id == user_id, Favorite.anime_id == anime_id)
            .first()
        )

    def list_for_user(self, user_id: str) -> list[Favorite]:
        return (
            self.db.query(Favorite)
            .filter(Favorite.user_id == user_id)
            .order_by(Favorite.created_at.desc())
            .all()
        )

    def add(self, user_id: str, anime_id: str) -> Favorite:
        existing = self.get(user_id, anime_id)
        if existing:
            return existing
        favorite = Favorite(user_id=user_id, anime_id=anime_id)
        self.db.add(favorite)
        self.db.commit()
        self.db.refresh(favorite)
        return favorite

    def remove(self, user_id: str, anime_id: str) -> bool:
        existing = self.get(user_id, anime_id)
        if not existing:
            return False
        self.db.delete(existing)
        self.db.commit()
        return True
