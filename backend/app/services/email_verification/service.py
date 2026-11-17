"""
Email-verification workflow: send link -> verify-email, plus resend.

Rules (rationale: docs/decisions/0006-email-verification.md):

- Only a SHA-256 hash of the token is stored. The raw token exists in the email
  body and in the request that redeems it - never in the DB, logs or responses.
- send/resend NEVER reveal whether an account exists: every outcome (unknown,
  inactive, already verified, throttled, delivery failure) returns None.
- Delivery failure is contained and logged by exception TYPE only. A user whose
  email failed can use resend; registration itself is not rolled back.
"""

from datetime import timedelta

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import create_email_verification_token, hash_email_verification_token
from app.integrations.email import EmailMessage, EmailSender
from app.models.user import User
from app.repositories.email_verification import EmailVerificationTokenRepository
from app.services.user import UserService

logger = get_logger(__name__)


class InvalidVerificationTokenError(Exception):
    """Unknown, expired or already-used token. One error on purpose."""


class EmailVerificationService:
    def __init__(
        self,
        user_service: UserService,
        repository: EmailVerificationTokenRepository,
        email_sender: EmailSender,
    ):
        self.user_service = user_service
        self.repository = repository
        self.email_sender = email_sender

    def send_verification_email(self, user: User) -> bool:
        """
        Issue a fresh token and email the link. Returns True only if the sender
        accepted the message. Never raises for delivery problems.

        Skipped (False) for inactive or already-verified users, and when the
        per-account cooldown / hourly cap is hit. Those limits are enforced
        atomically by the repository under a row lock (see issue_if_allowed);
        the email is sent only afterwards, with no database lock held.
        """
        # Read what we need now: issue_if_allowed ends the open transaction,
        # which expires ORM instances on this session.
        user_id, email = user.id, user.email

        settings = get_settings()
        raw_token = create_email_verification_token()
        try:
            outcome = self.repository.issue_if_allowed(
                user_id,
                hash_email_verification_token(raw_token),
                ttl=timedelta(minutes=settings.email_verification_token_expire_minutes),
                cooldown_seconds=settings.email_verification_resend_cooldown_seconds,
                max_per_hour=settings.email_verification_max_sends_per_hour,
            )
        except Exception as exc:
            # A lock timeout / deadlock must not fail registration or resend.
            logger.error(
                "verification token issue failed user_id=%s exception_type=%s",
                user_id,
                type(exc).__name__,
            )
            return False
        if outcome != "issued":
            logger.info("verification email not issued (%s) user_id=%s", outcome, user_id)
            return False

        # URL fragment: never sent to a server, so it can't reach access logs/Referer.
        url = f"{settings.frontend_base_url.rstrip('/')}/verify-email#token={raw_token}"
        hours = max(1, settings.email_verification_token_expire_minutes // 60)
        message = EmailMessage(
            to=email,
            subject="Verify your Anime Platform email address",
            body=(
                "Welcome to Anime Platform!\n\n"
                f"To verify your email address, open this link:\n{url}\n\n"
                f"The link works once and expires in {hours} hours. "
                "If you didn't create an account, ignore this email."
            ),
        )
        try:
            self.email_sender.send(message)
        except Exception as exc:
            logger.error(
                "verification email delivery failed user_id=%s exception_type=%s",
                user_id,
                type(exc).__name__,
            )
            return False
        logger.info("verification email sent user_id=%s", user_id)
        return True

    def resend_for_email(self, email: str) -> None:
        """Public resend. Identical (None) outcome for every address and state."""
        user = self.user_service.get_by_email(email)
        if user is None:
            logger.info("verification resend requested for an unknown account")
            return
        self.send_verification_email(user)

    def verify(self, raw_token: str) -> str:
        """Redeem a token. Returns the user id; raises InvalidVerificationTokenError."""
        user_id = self.repository.consume_and_verify(hash_email_verification_token(raw_token))
        if user_id is None:
            raise InvalidVerificationTokenError("Invalid or expired verification token")
        return user_id
