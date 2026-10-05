from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.services.user import UserService


class InvalidCredentialsError(Exception):
    pass


class AuthService:
    def __init__(self, user_service: UserService):
        self.user_service = user_service

    def authenticate(self, email: str, password: str) -> User:
        user = self.user_service.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError("Invalid email or password")
        if not user.is_active:
            raise InvalidCredentialsError("User account is inactive")
        return user

    def issue_token_for(self, user: User) -> str:
        return create_access_token(subject=user.id)
