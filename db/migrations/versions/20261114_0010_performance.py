"""Performance Intelligence : contenus publiés par Primestone et leurs métriques autorisées.

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
METRICS = (
    "views", "impressions", "ctr", "avg_view_duration_s", "avg_view_percentage",
    "watch_time_min", "likes", "comments", "subscribers_gained",
)  # fmt: skip


def upgrade() -> None:
    op.create_table(
        "content_item",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("language", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("script_id", UUID, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "language IS NULL OR language IN ('fr', 'en')", name=op.f("ck_content_item_language")
        ),
        sa.ForeignKeyConstraint(
            ["script_id"],
            ["script.id"],
            name=op.f("fk_content_item_script_id_script"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_content_item")),
        sa.UniqueConstraint(
            "platform", "external_id", name=op.f("uq_content_item_platform_external_id")
        ),
    )
    metrics = ", ".join(f"'{m}'" for m in METRICS)
    op.create_table(
        "performance_metric",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("content_id", UUID, nullable=False),
        sa.Column("metric", sa.Text(), nullable=False),
        sa.Column("value", sa.Numeric(18, 4), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("data_class", sa.Text(), nullable=False),
        sa.Column("imported_by", sa.Text(), nullable=False),
        sa.Column(
            "observed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(f"metric IN ({metrics})", name=op.f("ck_performance_metric_metric")),
        sa.CheckConstraint(
            "source IN ('YOUTUBE_STUDIO_CSV', 'YOUTUBE_ANALYTICS_API', 'MANUAL')",
            name=op.f("ck_performance_metric_source"),
        ),
        sa.CheckConstraint(
            "data_class = 'PRIVATE_AUTHORIZED'", name=op.f("ck_performance_metric_data_class")
        ),
        sa.CheckConstraint("value >= 0", name=op.f("ck_performance_metric_value")),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["content_item.id"],
            name=op.f("fk_performance_metric_content_id_content_item"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_performance_metric")),
    )
    op.create_index("ix_performance_metric_content_id", "performance_metric", ["content_id"])


def downgrade() -> None:
    # Réservé au développement et à la CI. Voir docs/operations/migrations.md.
    op.drop_index("ix_performance_metric_content_id", table_name="performance_metric")
    op.drop_table("performance_metric")
    op.drop_table("content_item")
