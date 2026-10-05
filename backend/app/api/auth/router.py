from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import get_auth_service, get_user_service
from app.core.logging import get_logger
from app.core.rate_limit import rate_limited
from app.schemas.auth import Token
from app.schemas.user import UserCreate, UserRead
from app.services.auth import AuthService, InvalidCredentialsError
from app.services.user import EmailAlreadyRegisteredError, UserService

router = APIRouter()
logger = get_logger(__name__)

# Auth-abuse protection only (see docs/decisions/0004-auth-rate-limiting.md):
# scoped to these two routes via `dependencies=[...]`, never a global
# middleware, so nothing else (public catalog/search/watch, or any
# already-authenticated endpoint) is affected.
REGISTER_RATE_LIMIT = Depends(rate_limited("register", max_requests=5, window_seconds=60))
LOGIN_RATE_LIMIT = Depends(rate_limited("login", max_requests=5, window_seconds=60))


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[REGISTER_RATE_LIMIT],
)
def register(data: UserCreate, user_service: UserService = Depends(get_user_service)) -> UserRead:
    try:
        user = user_service.register(data)
    except EmailAlreadyRegisteredError as exc:
        # Never log the email itself here - it's the user-supplied identity
        # of a request that just failed; logging it would let logs be used
        # to enumerate which addresses are already registered.
        logger.warning("registration failed: email already registered")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    logger.info("registration succeeded user_id=%s", user.id)
    return user


@router.post("/login", response_model=Token, dependencies=[LOGIN_RATE_LIMIT])
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(get_auth_service),
) -> Token:
    try:
        # OAuth2PasswordRequestForm uses "username" - we treat it as the email.
        user = auth_service.authenticate(form_data.username, form_data.password)
    except InvalidCredentialsError as exc:
        logger.warning("login failed: invalid credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    token = auth_service.issue_token_for(user)
    logger.info("login succeeded user_id=%s", user.id)
    return Token(access_token=token)
