from app.core.security import hash_password
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import UserCreate


class EmailAlreadyRegisteredError(Exception):
    pass


class UserService:
    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    def register(self, data: UserCreate) -> User:
        if self.user_repository.get_by_email(data.email):
            raise EmailAlreadyRegisteredError(f"{data.email} is already registered")

        user = User(
            email=data.email,
            hashed_password=hash_password(data.password),
            display_name=data.display_name,
        )
        return self.user_repository.create(user)

    def get_by_id(self, user_id: str) -> User | None:
        return self.user_repository.get_by_id(user_id)

    def get_by_email(self, email: str) -> User | None:
        return self.user_repository.get_by_email(email)
