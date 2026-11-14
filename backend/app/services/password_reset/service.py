"""
Password-reset workflow: forgot-password -> email -> reset-password.

Design rules this module exists to uphold (rationale and trade-offs:
docs/decisions/0005-password-reset.md):

- Requesting a reset NEVER reveals whether an account exists: the caller gets
  the same result for a registered, unregistered, or inactive address, and a
  failure to deliver the email is contained here rather than surfacing as an
  error that would only occur for real accounts.
- Raw tokens and reset links exist only in the email body and in the one
  request that redeems them. They are never stored (only a hash) and never
  logged.
"""

from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import (
    create_password_reset_token,
    hash_password,
    hash_password_reset_token,
)
from app.integrations.email import EmailMessage, EmailSender
from app.models.password_reset_token import PasswordResetToken
from app.repositories.password_reset import PasswordResetTokenRepository
from app.services.user import UserService

logger = get_logger(__name__)


class InvalidResetTokenError(Exception):
    """
    The token is unknown, expired, already used, or its account can't be
    reset. One error on purpose: callers must not be able to tell these apart.
    """


class PasswordResetService:
    def __init__(
        self,
        user_service: UserService,
        password_reset_repository: PasswordResetTokenRepository,
        email_sender: EmailSender,
    ):
        self.user_service = user_service
        self.password_reset_repository = password_reset_repository
        self.email_sender = email_sender

    def request_password_reset(self, email: str) -> None:
        """
        Emails a single-use reset link if `email` belongs to an active account.
        Returns None either way - callers cannot tell the cases apart.
        """
        user = self.user_service.get_by_email(email)
        if user is None or not user.is_active:
            logger.info("password reset requested for an unknown or inactive account")
            return

        settings = get_settings()
        raw_token = create_password_reset_token()
        expires_at = datetime.now(UTC) + timedelta(
            minutes=settings.password_reset_token_expire_minutes
        )
        # Only the hash is persisted. `raw_token` lives in this frame and in the
        # email body below, nowhere else.
        self.password_reset_repository.create(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hash_password_reset_token(raw_token),
                expires_at=expires_at,
            )
        )

        # URL fragment (#), not a query string: browsers never transmit the
        # fragment, so the token can't reach server access logs or Referer.
        reset_url = f"{settings.frontend_base_url.rstrip('/')}/reset-password#token={raw_token}"
        minutes = settings.password_reset_token_expire_minutes
        message = EmailMessage(
            to=user.email,
            subject="Reset your Anime Platform password",
            body=(
                "Someone asked to reset the password for your Anime Platform account.\n\n"
                f"To choose a new password, open this link:\n{reset_url}\n\n"
                f"The link works once and expires in {minutes} minutes. "
                "If you didn't ask for this, ignore this email - "
                "your password has not been changed."
            ),
        )
        try:
            self.email_sender.send(message)
        except Exception as exc:
            # Must be contained: if delivery errors surfaced to the client they
            # would happen only for real accounts, turning a failure into an
            # account-existence oracle. Log the exception TYPE only - never the
            # message, which a mail vendor's error could fill with the body/link.
            logger.error(
                "password reset email delivery failed user_id=%s exception_type=%s",
                user.id,
                type(exc).__name__,
            )
            return
        logger.info("password reset email sent user_id=%s", user.id)

    def reset_password(self, raw_token: str, new_password: str) -> str:
        """
        Redeems `raw_token` and sets `new_password`. Returns the user's id.
        Raises InvalidResetTokenError if the token can't be redeemed.

        Token consumption, the password change, and revoking the user's refresh
        sessions are one database transaction (see the repository method) -
        so a failure partway leaves the token unspent and the password unchanged.
        """
        # Argon2 is the slow step. Doing it BEFORE looking at the token means
        # response time doesn't depend on whether the token was valid.
        new_password_hash = hash_password(new_password)
        user_id = self.password_reset_repository.consume_and_reset_password(
            hash_password_reset_token(raw_token), new_password_hash
        )
        if user_id is None:
            raise InvalidResetTokenError("Invalid or expired reset token")
        return user_id
