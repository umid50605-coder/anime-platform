from datetime import UTC, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.email_verification_token import EmailVerificationToken
from app.models.user import User


class EmailVerificationTokenRepository:
    """Persistence operations for email-verification tokens."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, token: EmailVerificationToken) -> EmailVerificationToken:
        try:
            self.db.add(token)
            self.db.commit()
            self.db.refresh(token)
        except SQLAlchemyError:
            self.db.rollback()
            raise
        return token

    def issue_if_allowed(
        self,
        user_id: str,
        token_hash: str,
        *,
        ttl: timedelta,
        cooldown_seconds: int,
        max_per_hour: int,
        now: datetime | None = None,
    ) -> str:
        """
        Atomically apply the per-account resend limits and, only if they pass,
        store a new token. Returns "issued", "cooldown", "hourly_cap" or
        "ineligible" (user missing, inactive, or already verified).

        Concurrency: every caller for one user serialises on that user's row
        (SELECT ... FOR UPDATE) - the same lock consume_and_verify takes first -
        so locks are always user -> token and cannot deadlock. The limits are
        checked and the token inserted while the lock is held; commit releases
        it. The caller sends the email AFTER this returns, never under the lock.

        Snapshot caveat (MySQL REPEATABLE READ): a plain SELECT earlier in the
        same transaction (e.g. the user lookup that precedes a resend) pins the
        snapshot, and the count queries below would then miss a token another
        request committed while we waited for the lock. Ending the open
        transaction first makes the lock the transaction's first statement, so
        everything read after it sees all previously committed tokens. Nothing
        is written by the callers before this point, so nothing is discarded.
        """
        try:
            self.db.rollback()  # end any open read transaction (see above)
            state = (
                self.db.query(User.is_active, User.email_verified_at)
                .filter(User.id == user_id)
                .with_for_update()
                .one_or_none()
            )
            if state is None or not state.is_active or state.email_verified_at is not None:
                self.db.rollback()
                return "ineligible"

            # Taken AFTER the lock is acquired, so requests that queued for the
            # lock get monotonically increasing timestamps in lock order.
            current = now or datetime.now(UTC)

            recent = self.db.query(EmailVerificationToken.id).filter(
                EmailVerificationToken.user_id == user_id,
                EmailVerificationToken.created_at > current - timedelta(seconds=cooldown_seconds),
            )
            if recent.first() is not None:
                self.db.rollback()
                return "cooldown"

            in_last_hour = (
                self.db.query(func.count(EmailVerificationToken.id))
                .filter(
                    EmailVerificationToken.user_id == user_id,
                    EmailVerificationToken.created_at > current - timedelta(hours=1),
                )
                .scalar()
                or 0
            )
            if in_last_hour >= max_per_hour:
                self.db.rollback()
                return "hourly_cap"

            self.db.add(
                EmailVerificationToken(
                    user_id=user_id,
                    token_hash=token_hash,
                    created_at=current,
                    expires_at=current + ttl,
                )
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return "issued"

    def consume_and_verify(self, token_hash: str, now: datetime | None = None) -> str | None:
        """
        Spend a verification token and mark its user's email verified as ONE
        transaction (same shape as PasswordResetTokenRepository.
        consume_and_reset_password).

        0. look up the owning user_id by hash (plain read) and lock that user's
           row FIRST, so every attempt for one user serialises on the same row
           and locks are always taken user -> token (no lock-order cycle).
        1. consume the token with one conditional UPDATE (unused AND unexpired):
           of any number of concurrent attempts exactly one matches a row.
        2. set users.email_verified_at (kept if already set), active users only.
        3. expire the user's OTHER outstanding verification tokens.

        Any failure rolls everything back, so a token can never end up spent
        while the account stays unverified. Returns the user id, or None - with
        nothing changed - for an unknown, expired, used, or inactive-user token.
        """
        used_at = now or datetime.now(UTC)
        try:
            user_id = (
                self.db.query(EmailVerificationToken.user_id)
                .filter(EmailVerificationToken.token_hash == token_hash)
                .scalar()
            )
            if user_id is None:
                self.db.rollback()
                return None

            locked = (
                self.db.query(User.id).filter(User.id == user_id).with_for_update().scalar()
            )
            if locked is None:
                self.db.rollback()
                return None

            consumed = (
                self.db.query(EmailVerificationToken)
                .filter(
                    EmailVerificationToken.token_hash == token_hash,
                    EmailVerificationToken.used_at.is_(None),
                    EmailVerificationToken.expires_at > used_at,
                )
                .update({EmailVerificationToken.used_at: used_at}, synchronize_session=False)
            )
            if consumed == 0:
                self.db.rollback()
                return None

            updated_users = (
                self.db.query(User)
                .filter(User.id == user_id, User.is_active.is_(True))
                .update(
                    {User.email_verified_at: func.coalesce(User.email_verified_at, used_at)},
                    synchronize_session=False,
                )
            )
            if updated_users == 0:
                self.db.rollback()
                return None

            self.db.query(EmailVerificationToken).filter(
                EmailVerificationToken.user_id == user_id,
                EmailVerificationToken.used_at.is_(None),
            ).update({EmailVerificationToken.used_at: used_at}, synchronize_session=False)

            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return user_id
