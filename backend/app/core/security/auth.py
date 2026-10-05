"""
Security primitives: password hashing and JWT issuance/verification.

Kept deliberately small. Business rules (e.g. "who is allowed to log in")
belong in app/services/auth, not here - this module only knows how to hash a
password and how to encode/decode a token.
"""

import hashlib
import secrets
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


def create_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def create_password_reset_token() -> str:
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_password_reset_token(token: str) -> str:
    return hash_refresh_token(token)


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
    *,
    sid: str | None = None,
) -> str:
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload = {"sub": subject, "exp": expire}
    if sid is not None:
        payload["sid"] = sid
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    """Returns the subject (user id) encoded in the token, or None if invalid."""
    claims = decode_access_token_claims(token)
    subject = claims.get("sub") if claims is not None else None
    return subject if isinstance(subject, str) else None


def decode_access_token_claims(token: str) -> dict[str, object] | None:
    """Returns the decoded JWT claims, or None if the token is invalid."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload if isinstance(payload, dict) else None
    except JWTError:
        return None


def _get_validated_access_token_claims(token: str | None) -> dict[str, object]:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if token is None:
        logger.warning("unauthorized access attempt: no bearer token provided")
        raise credentials_exception
    claims = decode_access_token_claims(token)
    if claims is None or not isinstance(claims.get("sub"), str):
        logger.warning("unauthorized access attempt: invalid or expired token")
        raise credentials_exception
    return claims


def get_current_access_token_claims(
    token: str | None = Depends(oauth2_scheme),
) -> dict[str, object]:
    """Dependency for routes that need validated access-token claims."""
    return _get_validated_access_token_claims(token)
