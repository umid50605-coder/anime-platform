"""add email verification

Revision ID: b3d1c8a47e52
Revises: 6e4b7f9c2a11
Create Date: 2026-11-14

Adds users.email_verified_at and the email_verification_tokens table.
Existing users are backfilled as verified (email_verified_at = created_at) so
introducing verification can never lock anyone out of features they already use.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b3d1c8a47e52"
down_revision: str | Sequence[str] | None = "6e4b7f9c2a11"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    # Backfill: every user that exists at upgrade time is treated as verified.
    op.execute("UPDATE users SET email_verified_at = created_at WHERE email_verified_at IS NULL")

    op.create_table(
        "email_verification_tokens",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_email_verification_tokens_token_hash"),
        "email_verification_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        op.f("ix_email_verification_tokens_user_id"),
        "email_verification_tokens",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    # Dropping the table removes its indexes with it. They can't be dropped one
    # by one first: MySQL refuses to drop ix_..._user_id while the foreign key
    # on user_id still depends on it.
    op.drop_table("email_verification_tokens")
    op.drop_column("users", "email_verified_at")
