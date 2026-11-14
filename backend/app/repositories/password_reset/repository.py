from datetime import UTC, datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.password_reset_token import PasswordResetToken
from app.models.refresh_session import RefreshSession
from app.models.user import User


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
    

    def consume_and_reset_password(
        self,
        token_hash: str,
        new_password_hash: str,
        now: datetime | None = None,
    ) -> str | None:
        """
        Spend a reset token and apply the new password as ONE transaction.

        Everything below commits together or not at all:

        0. look up the owning user_id by token hash (plain read, no lock; the
           token may already be used or expired) and lock that user's row
           FIRST. Every reset attempt for one user therefore serialises on the
           same row, and locks are always taken in the order user -> token
           rows. This removes the user/token lock-order cycle (InnoDB error
           1213) that appeared when two different tokens of one user were
           redeemed concurrently.
        1. consume the token - only while it is unused and unexpired. This is
           a single conditional UPDATE, so of any number of concurrent attempts
           with the same token exactly one matches a row; the rest see
           `used_at` already set and match nothing. The database - not this
           Python code - is what makes the token single-use.
        2. set the user's password hash (active users only)
        3. expire any OTHER outstanding reset links for that user (the one just
           used is only one of possibly several still-valid emails)
        4. revoke every refresh session the user has, which also makes their
           existing access tokens fail the per-request session check

        Because steps 0-4 share one transaction, a failure anywhere after step
        1 rolls the token back to unused: a token can never end up spent while
        the password is unchanged. (mark_used_if_active, by contrast, commits
        on its own, so it cannot be used for this.)

        Returns the user's id on success, or None - with nothing changed - if
        the token is unknown, expired, already used, or its user is inactive.
        """
        used_at = now or datetime.now(UTC)
        try:
            user_id = (
                self.db.query(PasswordResetToken.user_id)
                .filter(PasswordResetToken.token_hash == token_hash)
                .scalar()
            )
            if user_id is None:
                self.db.rollback()
                return None

            # Lock the user row before any token row so that all attempts for
            # this user take locks in the same order. Ignored by SQLite.
            locked_user_id = (
                self.db.query(User.id)
                .filter(User.id == user_id)
                .with_for_update()
                .scalar()
            )
            if locked_user_id is None:
                self.db.rollback()
                return None

            consumed = (
                self.db.query(PasswordResetToken)
                .filter(
                    PasswordResetToken.token_hash == token_hash,
                    PasswordResetToken.used_at.is_(None),
                    PasswordResetToken.expires_at > used_at,
                )
                .update({PasswordResetToken.used_at: used_at}, synchronize_session=False)
            )
            if consumed == 0:
                self.db.rollback()
                return None

            updated_users = (
                self.db.query(User)
                .filter(User.id == user_id, User.is_active.is_(True))
                .update({User.hashed_password: new_password_hash}, synchronize_session=False)
            )
            if updated_users == 0:
                self.db.rollback()
                return None

            self.db.query(PasswordResetToken).filter(
                PasswordResetToken.user_id == user_id,
                PasswordResetToken.used_at.is_(None),
            ).update({PasswordResetToken.used_at: used_at}, synchronize_session=False)

            self.db.query(RefreshSession).filter(
                RefreshSession.user_id == user_id,
                RefreshSession.revoked_at.is_(None),
            ).update({RefreshSession.revoked_at: used_at}, synchronize_session=False)

            self.db.commit()
        except Exception:
            # Deliberately broader than SQLAlchemyError: whatever interrupts the
            # transaction midway, the token must not stay consumed.
            self.db.rollback()
            raise
        return user_id