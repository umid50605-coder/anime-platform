from datetime import UTC, datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.password_reset_token import PasswordResetToken


class PasswordResetTokenRepository:
    """Persistence operations for password-reset tokens."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_token_hash(self, token_hash: str) -> PasswordResetToken | None:
        return (
            self.db.query(PasswordResetToken)
            .filter(PasswordResetToken.token_hash == token_hash)
            .populate_existing()
            .first()
        )

    def create(self, token: PasswordResetToken) -> PasswordResetToken:
        """Persist and return a new password-reset token."""
        try:
            self.db.add(token)
            self.db.commit()
            self.db.refresh(token)
        except SQLAlchemyError:
            self.db.rollback()
            raise
        return token

    def mark_used_if_active(self, token_hash: str, now: datetime | None = None) -> bool:
        """Atomically consume a token only while it remains unused and unexpired."""
        used_at = now or datetime.now(UTC)
        try:
            updated_count = (
                self.db.query(PasswordResetToken)
                .filter(
                    PasswordResetToken.token_hash == token_hash,
                    PasswordResetToken.used_at.is_(None),
                    PasswordResetToken.expires_at > used_at,
                )
                .update(
                    {PasswordResetToken.used_at: used_at},
                    synchronize_session="fetch",
                )
            )
            if updated_count == 0:
                self.db.rollback()
                return False
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise
        return True
