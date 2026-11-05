"""add provider-independent anime external mappings

Revision ID: 6e4b7f9c2a11
Revises: 25f3b8c1d7a4
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6e4b7f9c2a11"
down_revision: str | Sequence[str] | None = "25f3b8c1d7a4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_anime_provider_external_id",
        "anime",
        ["external_provider", "external_id"],
        unique=True,
    )
    op.create_index(
        "uq_anime_external_episode",
        "episodes",
        ["anime_id", "external_episode_id"],
        unique=True,
    )
    op.create_table(
        "anime_external_ids",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("anime_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("external_id", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["anime_id"], ["anime.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider", "external_id", name="uq_mapping_provider_external_id"
        ),
    )
    op.create_index(
        "ix_anime_external_ids_anime_id", "anime_external_ids", ["anime_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_anime_external_ids_anime_id", table_name="anime_external_ids")
    op.drop_table("anime_external_ids")
    op.drop_index("uq_anime_external_episode", table_name="episodes")
    op.drop_index("uq_anime_provider_external_id", table_name="anime")
