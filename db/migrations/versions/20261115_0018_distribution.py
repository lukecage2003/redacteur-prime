"""Distribution et portefeuille : canaux, plan de diffusion (proposé, approuvé, publié
déclaré), portefeuilles à objectifs d'équilibre, canal des contenus.

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def _id() -> sa.Column:  # type: ignore[type-arg]
    return sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False)


def _created() -> sa.Column:  # type: ignore[type-arg]
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def _fk(table: str, column: str, target: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], [f"{target}.id"], name=op.f(f"fk_{table}_{column}_{target}"), ondelete="RESTRICT"
    )


def upgrade() -> None:
    op.create_table(
        "distribution_channel",
        _id(),
        sa.Column("brand_id", UUID, nullable=False),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("handle", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'ACTIVE'"), nullable=False),
        sa.Column(
            "stats_authorization", sa.Text(), server_default=sa.text("'NONE'"), nullable=False
        ),
        _created(),
        sa.CheckConstraint(
            "language IN ('fr', 'en')", name=op.f("ck_distribution_channel_language")
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'PAUSED', 'RETIRED')", name=op.f("ck_distribution_channel_status")
        ),
        sa.CheckConstraint(
            "stats_authorization IN ('NONE', 'CSV_EXPORT', 'OAUTH_READONLY')",
            name=op.f("ck_distribution_channel_stats_authorization"),
        ),
        _fk("distribution_channel", "brand_id", "media_brand"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_distribution_channel")),
        sa.UniqueConstraint(
            "platform", "handle", name=op.f("uq_distribution_channel_platform_handle")
        ),
    )
    op.create_table(
        "distribution_item",
        _id(),
        sa.Column("channel_id", UUID, nullable=False),
        sa.Column("script_id", UUID, nullable=True),
        sa.Column("series_id", UUID, nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("format", sa.Text(), nullable=True),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'PROPOSED'"), nullable=False),
        sa.Column("content_id", UUID, nullable=True),
        sa.Column("published_url", sa.Text(), nullable=True),
        sa.Column("declared_by", sa.Text(), nullable=True),
        sa.Column("declared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=False),
        _created(),
        sa.CheckConstraint(
            "status IN ('PROPOSED', 'APPROVED', 'PUBLISHED', 'CANCELLED')",
            name=op.f("ck_distribution_item_status"),
        ),
        sa.CheckConstraint(
            "status <> 'PUBLISHED' OR (content_id IS NOT NULL AND declared_by IS NOT NULL)",
            name=op.f("ck_distribution_item_declared"),
        ),
        _fk("distribution_item", "channel_id", "distribution_channel"),
        _fk("distribution_item", "script_id", "script"),
        _fk("distribution_item", "series_id", "series"),
        _fk("distribution_item", "content_id", "content_item"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_distribution_item")),
    )
    op.create_table(
        "content_portfolio",
        _id(),
        sa.Column("brand_id", UUID, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("targets", postgresql.JSONB(), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        _created(),
        sa.CheckConstraint("period_end >= period_start", name=op.f("ck_content_portfolio_period")),
        _fk("content_portfolio", "brand_id", "media_brand"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_content_portfolio")),
        sa.UniqueConstraint("brand_id", "name", name=op.f("uq_content_portfolio_brand_id_name")),
    )
    op.add_column("content_item", sa.Column("channel_id", UUID, nullable=True))
    op.create_foreign_key(
        op.f("fk_content_item_channel_id_distribution_channel"),
        "content_item",
        "distribution_channel",
        ["channel_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    # Réservé au développement et à la CI. Voir docs/operations/migrations.md.
    op.drop_constraint(
        op.f("fk_content_item_channel_id_distribution_channel"), "content_item", type_="foreignkey"
    )
    op.drop_column("content_item", "channel_id")
    op.drop_table("content_portfolio")
    op.drop_table("distribution_item")
    op.drop_table("distribution_channel")
