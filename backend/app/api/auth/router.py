from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import get_auth_service, get_user_service
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.rate_limit import rate_limited
from app.schemas.auth import Token
from app.schemas.user import UserCreate, UserRead
from app.services.auth import AuthService, InvalidCredentialsError, InvalidRefreshTokenError
from app.services.user import EmailAlreadyRegisteredError, UserService

router = APIRouter()
logger = get_logger(__name__)

# Auth-abuse protection only (see docs/decisions/0004-auth-rate-limiting.md):
# scoped to these auth routes via `dependencies=[...]`, never a global
# middleware, so unrelated public and authenticated endpoints are unaffected.
REGISTER_RATE_LIMIT = Depends(rate_limited("register", max_requests=5, window_seconds=60))
LOGIN_RATE_LIMIT = Depends(rate_limited("login", max_requests=5, window_seconds=60))
REFRESH_RATE_LIMIT = Depends(rate_limited("refresh", max_requests=5, window_seconds=60))


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="lax",
        secure=settings.environment == "production",
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path="/api/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        samesite="lax",
        secure=get_settings().environment == "production",
        path="/api/auth",
    )


def require_allowed_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin is None or origin not in get_settings().cors_allow_origins:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Origin not allowed")


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
    response: Response,
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
    tokens = auth_service.create_login_session(user)
    _set_refresh_cookie(response, tokens.refresh_token)
    logger.info("login succeeded user_id=%s", user.id)
    return Token(access_token=tokens.access_token)


@router.post(
    "/refresh",
    response_model=Token,
    dependencies=[Depends(require_allowed_origin), REFRESH_RATE_LIMIT],
)
def refresh(
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
) -> Token | JSONResponse:
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token is None:
        invalid_response = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid refresh token"},
            headers={"WWW-Authenticate": "Bearer"},
        )
        _clear_refresh_cookie(invalid_response)
        return invalid_response

    try:
        tokens = auth_service.refresh_session(refresh_token)
    except InvalidRefreshTokenError:
        invalid_response = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid refresh token"},
            headers={"WWW-Authenticate": "Bearer"},
        )
        _clear_refresh_cookie(invalid_response)
        return invalid_response

    _set_refresh_cookie(response, tokens.refresh_token)
    return Token(access_token=tokens.access_token)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_allowed_origin)],
)
def logout(
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
) -> Response:
    auth_service.logout_session(request.cookies.get("refresh_token"))
    _clear_refresh_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
