"""Market Intelligence : sources avec fiche, collectes tracées, contenus publics, métriques
publiques horodatées, sujets.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()


def _id() -> sa.Column:  # type: ignore[type-arg]
    return sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False)


def _now(name: str) -> sa.Column:  # type: ignore[type-arg]
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def _source_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["source_id"],
        ["market_source.id"],
        name=op.f(f"fk_{table}_source_id_market_source"),
        ondelete="RESTRICT",
    )


def upgrade() -> None:
    op.create_table(
        "market_source",
        _id(),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("access", sa.Text(), nullable=False),
        sa.Column("quota", sa.Text(), nullable=False),
        sa.Column("terms_url", sa.Text(), nullable=False),
        sa.Column("data_class", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=True),
        sa.Column("config", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_by", sa.Text(), nullable=True),
        _now("created_at"),
        sa.CheckConstraint(
            "kind IN ('YOUTUBE_API', 'RSS', 'MANUAL')", name=op.f("ck_market_source_kind")
        ),
        sa.CheckConstraint(
            "data_class IN ('PUBLIC', 'ESTIMATE', 'HYPOTHESIS')",
            name=op.f("ck_market_source_data_class"),
        ),
        sa.CheckConstraint(
            "language IS NULL OR language IN ('fr', 'en')", name=op.f("ck_market_source_language")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_market_source")),
        sa.UniqueConstraint("key", name=op.f("uq_market_source_key")),
    )
    op.create_table(
        "market_collection",
        _id(),
        sa.Column("source_id", UUID, nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("params", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("items", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("metrics", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("quota_units", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("author", sa.Text(), nullable=False),
        _now("started_at"),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('RUNNING', 'SUCCEEDED', 'FAILED')", name=op.f("ck_market_collection_status")
        ),
        _source_fk("market_collection"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_market_collection")),
    )
    op.create_index("ix_market_collection_source_id", "market_collection", ["source_id"])
    op.create_table(
        "market_item",
        _id(),
        sa.Column("source_id", UUID, nullable=False),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("channel", sa.Text(), nullable=True),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        _now("first_seen_at"),
        sa.CheckConstraint("language IN ('fr', 'en')", name=op.f("ck_market_item_language")),
        _source_fk("market_item"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_market_item")),
        sa.UniqueConstraint(
            "platform", "external_id", name=op.f("uq_market_item_platform_external_id")
        ),
    )
    op.create_table(
        "market_metric",
        _id(),
        sa.Column("item_id", UUID, nullable=False),
        sa.Column("collection_id", UUID, nullable=False),
        sa.Column("metric", sa.Text(), nullable=False),
        sa.Column("value", sa.BigInteger(), nullable=False),
        sa.Column("data_class", sa.Text(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "metric IN ('views', 'likes', 'comments')", name=op.f("ck_market_metric_metric")
        ),
        sa.CheckConstraint("data_class = 'PUBLIC'", name=op.f("ck_market_metric_data_class")),
        sa.CheckConstraint("value >= 0", name=op.f("ck_market_metric_value")),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["market_item.id"],
            name=op.f("fk_market_metric_item_id_market_item"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["collection_id"],
            ["market_collection.id"],
            name=op.f("fk_market_metric_collection_id_market_collection"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_market_metric")),
        sa.UniqueConstraint(
            "item_id",
            "metric",
            "observed_at",
            name=op.f("uq_market_metric_item_id_metric_observed_at"),
        ),
    )
    op.create_table(
        "market_topic",
        _id(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("keywords_fr", JSONB, nullable=False),
        sa.Column("keywords_en", JSONB, nullable=False),
        sa.Column("author", sa.Text(), nullable=False),
        _now("created_at"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_market_topic")),
        sa.UniqueConstraint("name", name=op.f("uq_market_topic_name")),
    )


def downgrade() -> None:
    # Réservé au développement et à la CI. Voir docs/operations/migrations.md.
    op.drop_table("market_topic")
    op.drop_table("market_metric")
    op.drop_table("market_item")
    op.drop_index("ix_market_collection_source_id", table_name="market_collection")
    op.drop_table("market_collection")
    op.drop_table("market_source")
