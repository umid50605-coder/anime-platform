from functools import lru_cache

from app.core.config import get_settings
from app.core.logging import get_logger
from app.integrations.email.memory_sender import InMemoryEmailSender
from app.integrations.email.sender import EmailSender

logger = get_logger(__name__)


@lru_cache
def get_email_sender() -> EmailSender:
    """
    Returns the configured EmailSender implementation ("memory" or "smtp").

    Cached so every dependency injection across the process shares one
    instance - the same pattern get_anime_provider/get_video_provider use.
    """
    settings = get_settings()
    if settings.email_provider == "memory":
        if settings.environment == "production":
            # Not an error (nothing else exists yet), but an operator must not
            # discover this only when users report missing reset emails.
            logger.warning(
                "email_provider=memory in production: emails are NOT delivered "
                "(password reset links will never reach users)"
            )
        return InMemoryEmailSender()
    if settings.email_provider == "smtp":
        from app.integrations.email.smtp_sender import SmtpEmailSender

        return SmtpEmailSender(
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            from_address=settings.email_from_address,
            from_name=settings.email_from_name,
            use_tls=settings.smtp_use_tls,
            use_ssl=settings.smtp_use_ssl,
            timeout_seconds=settings.smtp_timeout_seconds,
        )
    raise ValueError(f"Unknown email_provider setting: {settings.email_provider}")


def reset_email_sender() -> None:
    """
    Test-only: empties the in-memory outbox without discarding the cached
    instance. Production code never calls this - see tests/backend/conftest.py.
    """
    sender = get_email_sender()
    if isinstance(sender, InMemoryEmailSender):
        sender.clear()
