"""
Security primitives: password hashing and JWT issuance/verification.

Kept deliberately small. Business rules (e.g. "who is allowed to log in")
belong in app/services/auth, not here - this module only knows how to hash a
password and how to encode/decode a token.
"""

from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)
# Argon2id (OWASP's current recommended default for password hashing).
# NOTE: an earlier version of this file used passlib's "bcrypt" scheme, but
# passlib 1.7.4 (unmaintained since 2020) has a self-test that is
# incompatible with bcrypt>=4.1 and raises ValueError on every hash call.
# Argon2 does not have this issue and is arguably the better default anyway.
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# tokenUrl points at the login endpoint - only used for OpenAPI docs / the
# "Authorize" button, not for routing.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    """Returns the subject (user id) encoded in the token, or None if invalid."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload.get("sub")
    except JWTError:
        return None


def get_current_user_id(
    token: str = Depends(oauth2_scheme),
) -> str:
    """
    Dependency for routes that require authentication.

    Only decodes the token and returns the user id. Whether that user still
    exists / is active is a concern for the user service+repository, not for
    this security module.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if token is None:
        logger.warning("unauthorized access attempt: no bearer token provided")
        raise credentials_exception
    user_id = decode_access_token(token)
    if user_id is None:
        logger.warning("unauthorized access attempt: invalid or expired token")
        raise credentials_exception
    return user_id
