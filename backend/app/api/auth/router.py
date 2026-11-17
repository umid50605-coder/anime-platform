from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import (
    get_auth_service,
    get_email_verification_service,
    get_password_reset_service,
    get_user_service,
)
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.rate_limit import rate_limited
from app.schemas.auth import (
    ForgotPasswordRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    Token,
    VerifyEmailRequest,
)
from app.schemas.common import MessageResponse
from app.schemas.user import UserCreate, UserRead
from app.services.auth import AuthService, InvalidCredentialsError, InvalidRefreshTokenError
from app.services.email_verification import (
    EmailVerificationService,
    InvalidVerificationTokenError,
)
from app.services.password_reset import InvalidResetTokenError, PasswordResetService
from app.services.user import EmailAlreadyRegisteredError, UserService

router = APIRouter()
logger = get_logger(__name__)

# Auth-abuse protection only (see docs/decisions/0004-auth-rate-limiting.md):
# scoped to these auth routes via `dependencies=[...]`, never a global
# middleware, so unrelated public and authenticated endpoints are unaffected.
REGISTER_RATE_LIMIT = Depends(rate_limited("register", max_requests=5, window_seconds=60))
LOGIN_RATE_LIMIT = Depends(rate_limited("login", max_requests=5, window_seconds=60))
REFRESH_RATE_LIMIT = Depends(rate_limited("refresh", max_requests=5, window_seconds=60))
# Same per-IP convention for the password-reset pair; each action keeps its own counter.
FORGOT_PASSWORD_RATE_LIMIT = Depends(
    rate_limited("forgot_password", max_requests=5, window_seconds=60)
)
RESET_PASSWORD_RATE_LIMIT = Depends(
    rate_limited("reset_password", max_requests=5, window_seconds=60)
)

# Email verification: same per-IP convention, each action with its own counter.
# Per-ACCOUNT resend limits live in EmailVerificationService (DB-backed).
VERIFY_EMAIL_RATE_LIMIT = Depends(rate_limited("verify_email", max_requests=5, window_seconds=60))
RESEND_VERIFICATION_RATE_LIMIT = Depends(
    rate_limited("resend_verification", max_requests=5, window_seconds=60)
)

# Identical text for every resend-verification outcome.
RESEND_VERIFICATION_MESSAGE = (
    "If an account exists for that email address and it is not verified yet, "
    "we have sent it a verification link."
)

# Identical text for every forgot-password outcome - see PasswordResetService.
FORGOT_PASSWORD_MESSAGE = (
    "If an account exists for that email address, we have sent it password reset instructions."
)


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
def register(
    data: UserCreate,
    user_service: UserService = Depends(get_user_service),
    verification_service: EmailVerificationService = Depends(get_email_verification_service),
) -> UserRead:
    try:
        user = user_service.register(data)
    except EmailAlreadyRegisteredError as exc:
        # Never log the email itself here - it's the user-supplied identity
        # of a request that just failed; logging it would let logs be used
        # to enumerate which addresses are already registered.
        logger.warning("registration failed: email already registered")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    logger.info("registration succeeded user_id=%s", user.id)
    # Contained: a delivery failure never fails registration (user can resend).
    verification_service.send_verification_email(user)
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


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[FORGOT_PASSWORD_RATE_LIMIT],
)
def forgot_password(
    data: ForgotPasswordRequest,
    password_reset_service: PasswordResetService = Depends(get_password_reset_service),
) -> MessageResponse:
    # Same status and body whether or not the address is registered. No origin
    # check: this endpoint is not cookie-authenticated, so there is no ambient
    # credential for a cross-site request to abuse.
    password_reset_service.request_password_reset(data.email)
    return MessageResponse(detail=FORGOT_PASSWORD_MESSAGE)


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    dependencies=[RESET_PASSWORD_RATE_LIMIT],
)
def reset_password(
    data: ResetPasswordRequest,
    password_reset_service: PasswordResetService = Depends(get_password_reset_service),
) -> MessageResponse:
    try:
        user_id = password_reset_service.reset_password(data.token, data.new_password)
    except InvalidResetTokenError as exc:
        # One generic 400 for unknown, expired, and already-used tokens alike.
        logger.warning("password reset failed: invalid, expired, or already-used token")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        ) from exc
    logger.info("password reset succeeded user_id=%s", user_id)
    return MessageResponse(detail="Your password has been reset. You can now sign in.")


@router.post(
    "/verify-email",
    response_model=MessageResponse,
    dependencies=[VERIFY_EMAIL_RATE_LIMIT],
)
def verify_email(
    data: VerifyEmailRequest,
    verification_service: EmailVerificationService = Depends(get_email_verification_service),
) -> MessageResponse:
    try:
        user_id = verification_service.verify(data.token)
    except InvalidVerificationTokenError as exc:
        # One generic 400 for unknown, expired and already-used tokens alike.
        logger.warning("email verification failed: invalid, expired, or already-used token")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        ) from exc
    logger.info("email verification succeeded user_id=%s", user_id)
    return MessageResponse(detail="Your email address has been verified.")


@router.post(
    "/resend-verification",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[RESEND_VERIFICATION_RATE_LIMIT],
)
def resend_verification(
    data: ResendVerificationRequest,
    verification_service: EmailVerificationService = Depends(get_email_verification_service),
) -> MessageResponse:
    # Same status and body whether or not the address is registered, verified,
    # throttled, or delivery failed.
    verification_service.resend_for_email(data.email)
    return MessageResponse(detail=RESEND_VERIFICATION_MESSAGE)
