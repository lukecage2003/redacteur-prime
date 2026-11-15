"""Creative Intelligence : charte de marque versionnée, séries et épisodes, packaging.

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()


def _id() -> sa.Column:  # type: ignore[type-arg]
    return sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False)


def _now(name: str) -> sa.Column:  # type: ignore[type-arg]
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def _fk(table: str, column: str, target: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], [f"{target}.id"], name=op.f(f"fk_{table}_{column}_{target}"), ondelete="RESTRICT"
    )


def upgrade() -> None:
    op.create_table(
        "brand_charter",
        _id(),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("rules", JSONB, nullable=False),
        sa.Column("author", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        _now("created_at"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_brand_charter")),
        sa.UniqueConstraint("version", name=op.f("uq_brand_charter_version")),
    )
    op.create_table(
        "series",
        _id(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("promise", sa.Text(), nullable=False),
        sa.Column("identity", sa.Text(), nullable=False),
        sa.Column("segment_id", UUID, nullable=True),
        sa.Column("tone", sa.Text(), nullable=False),
        sa.Column("structure", JSONB, nullable=False),
        sa.Column("target_minutes", sa.Integer(), nullable=False),
        sa.Column("art_direction", sa.Text(), nullable=False),
        sa.Column("distribution", JSONB, nullable=False),
        sa.Column("evolution", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'ACTIVE'"), nullable=False),
        sa.Column("author", sa.Text(), nullable=False),
        _now("created_at"),
        _now("updated_at"),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'PAUSED', 'ENDED')", name=op.f("ck_series_status")
        ),
        sa.CheckConstraint(
            "target_minutes > 0 AND target_minutes <= 240", name=op.f("ck_series_target_minutes")
        ),
        _fk("series", "segment_id", "audience_segment"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_series")),
        sa.UniqueConstraint("name", name=op.f("uq_series_name")),
    )
    op.create_table(
        "series_episode",
        _id(),
        sa.Column("series_id", UUID, nullable=False),
        sa.Column("script_id", UUID, nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        _now("created_at"),
        _fk("series_episode", "series_id", "series"),
        _fk("series_episode", "script_id", "script"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_series_episode")),
        sa.UniqueConstraint("series_id", "number", name=op.f("uq_series_episode_series_id_number")),
        sa.UniqueConstraint("script_id", name=op.f("uq_series_episode_script_id")),
    )
    op.create_table(
        "packaging_set",
        _id(),
        sa.Column("script_id", UUID, nullable=False),
        sa.Column("script_version", sa.Integer(), nullable=False),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column("charter_version", sa.Integer(), nullable=True),
        sa.Column("content", JSONB, nullable=False),
        _now("created_at"),
        _fk("packaging_set", "script_id", "script"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_packaging_set")),
    )
    op.create_index("ix_packaging_set_script_id", "packaging_set", ["script_id"])


def downgrade() -> None:
    # Réservé au développement et à la CI. Voir docs/operations/migrations.md.
    op.drop_index("ix_packaging_set_script_id", table_name="packaging_set")
    op.drop_table("packaging_set")
    op.drop_table("series_episode")
    op.drop_table("series")
    op.drop_table("brand_charter")
