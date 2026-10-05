from datetime import UTC, datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.refresh_session import RefreshSession


class RefreshSessionRepository:
    """Persistence operations for refresh-token sessions."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_token_hash(self, token_hash: str) -> RefreshSession | None:
        return (
            self.db.query(RefreshSession)
            .filter(RefreshSession.token_hash == token_hash)
            .populate_existing()
            .first()
        )

    def has_active_family(self, user_id: str, family_id: str) -> bool:
        refresh_session = (
            self.db.query(RefreshSession)
            .filter(
                RefreshSession.user_id == user_id,
                RefreshSession.family_id == family_id,
                RefreshSession.revoked_at.is_(None),
            )
            .populate_existing()
            .first()
        )
        if refresh_session is None:
            return False

        expires_at = refresh_session.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        else:
            expires_at = expires_at.astimezone(UTC)
        return expires_at > datetime.now(UTC)

    def create(self, refresh_session: RefreshSession) -> RefreshSession:
        """Persist and return a new refresh session."""
        try:
            self.db.add(refresh_session)
            self.db.commit()
            self.db.refresh(refresh_session)
        except SQLAlchemyError:
            self.db.rollback()
            raise
        return refresh_session

    def revoke_session(self, session_id: str) -> bool:
        """Revoke an active session and commit the change."""
        try:
            result = (
                self.db.query(RefreshSession)
                .filter(
                    RefreshSession.id == session_id,
                    RefreshSession.revoked_at.is_(None),
                )
                .update(
                    {RefreshSession.revoked_at: datetime.now(UTC)},
                    synchronize_session="fetch",
                )
            )
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise
        return result > 0

    def revoke_family(self, family_id: str) -> int:
        """Revoke and commit all active sessions in a family."""
        now = datetime.now(UTC)
        try:
            revoked_count = (
                self.db.query(RefreshSession)
                .filter(
                    RefreshSession.family_id == family_id,
                    RefreshSession.revoked_at.is_(None),
                )
                .update(
                    {RefreshSession.revoked_at: now},
                    synchronize_session="fetch",
                )
            )
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise
        return revoked_count

    def rotate(self, token_hash: str, replacement: RefreshSession) -> bool:
        """Atomically revoke the old token and persist its replacement.

        A single conditional UPDATE prevents expired or already-revoked tokens
        from being reused. Both database changes are committed together.
        """
        now = datetime.now(UTC)
        try:
            revoked_count = (
                self.db.query(RefreshSession)
                .filter(
                    RefreshSession.token_hash == token_hash,
                    RefreshSession.revoked_at.is_(None),
                    RefreshSession.expires_at > now,
                )
                .update(
                    {RefreshSession.revoked_at: now},
                    synchronize_session="fetch",
                )
            )
            if revoked_count == 0:
                self.db.rollback()
                return False

            self.db.add(replacement)
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise

        return True
