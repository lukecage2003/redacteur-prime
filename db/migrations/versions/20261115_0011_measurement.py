"""Mesure par objectif et expérimentation : objectifs et formats de contenu, métriques
élargies, segments agrégés, courbes de rétention, expériences.

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
OLD = (
    "views", "impressions", "ctr", "avg_view_duration_s", "avg_view_percentage",
    "watch_time_min", "likes", "comments", "subscribers_gained",
)  # fmt: skip
NEW = (*OLD, "subscribers_lost", "shares", "saves", "returning_viewers", "new_viewers",
       "unique_viewers", "engaged_views")  # fmt: skip


def _in(values: Sequence[str], column: str) -> str:
    return f"{column} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def _now(name: str) -> sa.Column:  # type: ignore[type-arg]
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def upgrade() -> None:
    op.add_column("content_item", sa.Column("objective", sa.Text(), nullable=True))
    op.add_column("content_item", sa.Column("format", sa.Text(), nullable=True))
    op.create_check_constraint(
        op.f("ck_content_item_objective"),
        "content_item",
        "objective IS NULL OR "
        + _in(("DISCOVERY", "EXPLORATION", "EXPERTISE", "COMMUNITY"), "objective"),
    )
    op.create_check_constraint(
        op.f("ck_content_item_format"),
        "content_item",
        "format IS NULL OR "
        + _in(("LONG", "SHORT", "REEL", "CAROUSEL", "POST", "PODCAST", "LIVE"), "format"),
    )
    op.drop_constraint(op.f("ck_performance_metric_metric"), "performance_metric", type_="check")
    op.create_check_constraint(
        op.f("ck_performance_metric_metric"), "performance_metric", _in(NEW, "metric")
    )
    op.add_column("performance_metric", sa.Column("dimension", sa.Text(), nullable=True))
    op.add_column("performance_metric", sa.Column("dimension_value", sa.Text(), nullable=True))
    op.create_check_constraint(
        op.f("ck_performance_metric_dimension"),
        "performance_metric",
        "dimension IS NULL OR "
        + _in(
            ("traffic_source", "country", "age_group", "device", "subscribed_status"), "dimension"
        ),
    )
    op.create_table(
        "retention_point",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("content_id", UUID, nullable=False),
        sa.Column("elapsed_ratio", sa.Numeric(6, 4), nullable=False),
        sa.Column("audience_watch_ratio", sa.Numeric(8, 4), nullable=False),
        sa.Column("relative_performance", sa.Numeric(8, 4), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        _now("observed_at"),
        sa.CheckConstraint(
            "elapsed_ratio >= 0 AND elapsed_ratio <= 1",
            name=op.f("ck_retention_point_elapsed_ratio"),
        ),
        sa.CheckConstraint(
            "audience_watch_ratio >= 0", name=op.f("ck_retention_point_audience_watch_ratio")
        ),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["content_item.id"],
            name=op.f("fk_retention_point_content_id_content_item"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_retention_point")),
        sa.UniqueConstraint(
            "content_id",
            "elapsed_ratio",
            "observed_at",
            name=op.f("uq_retention_point_content_id_elapsed_ratio_observed_at"),
        ),
    )
    op.create_table(
        "experiment",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("hypothesis", sa.Text(), nullable=False),
        sa.Column("variable", sa.Text(), nullable=False),
        sa.Column("audience", sa.Text(), nullable=True),
        sa.Column("format", sa.Text(), nullable=True),
        sa.Column("metric", sa.Text(), nullable=False),
        sa.Column(
            "content_ids", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'PLANNED'"), nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("conclusion", sa.Text(), nullable=True),
        sa.Column("next_experiment", sa.Text(), nullable=True),
        sa.Column("author", sa.Text(), nullable=False),
        _now("created_at"),
        _now("updated_at"),
        sa.CheckConstraint(
            _in(("TITLE", "THUMBNAIL", "HOOK", "PROMISE", "FORMAT", "LENGTH", "OTHER"), "variable"),
            name=op.f("ck_experiment_variable"),
        ),
        sa.CheckConstraint(
            _in(("PLANNED", "RUNNING", "CONCLUDED", "INCONCLUSIVE"), "status"),
            name=op.f("ck_experiment_status"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_experiment")),
    )
    op.create_table(
        "experiment_variant",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("experiment_id", UUID, nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("exposures", sa.BigInteger(), nullable=True),
        sa.Column("successes", sa.BigInteger(), nullable=True),
        sa.Column("reported_share", sa.Numeric(6, 4), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        _now("created_at"),
        sa.CheckConstraint(
            "exposures IS NULL OR (exposures >= 0 AND successes >= 0 AND successes <= exposures)",
            name=op.f("ck_experiment_variant_counts"),
        ),
        sa.CheckConstraint(
            "reported_share IS NULL OR (reported_share >= 0 AND reported_share <= 1)",
            name=op.f("ck_experiment_variant_reported_share"),
        ),
        sa.ForeignKeyConstraint(
            ["experiment_id"],
            ["experiment.id"],
            name=op.f("fk_experiment_variant_experiment_id_experiment"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_experiment_variant")),
        sa.UniqueConstraint(
            "experiment_id", "label", name=op.f("uq_experiment_variant_experiment_id_label")
        ),
    )


def downgrade() -> None:
    # Réservé au développement et à la CI. Voir docs/operations/migrations.md.
    op.drop_table("experiment_variant")
    op.drop_table("experiment")
    op.drop_table("retention_point")
    op.drop_constraint(op.f("ck_performance_metric_dimension"), "performance_metric", type_="check")
    op.drop_column("performance_metric", "dimension_value")
    op.drop_column("performance_metric", "dimension")
    op.drop_constraint(op.f("ck_performance_metric_metric"), "performance_metric", type_="check")
    op.create_check_constraint(
        op.f("ck_performance_metric_metric"), "performance_metric", _in(OLD, "metric")
    )
    op.drop_constraint(op.f("ck_content_item_format"), "content_item", type_="check")
    op.drop_constraint(op.f("ck_content_item_objective"), "content_item", type_="check")
    op.drop_column("content_item", "format")
    op.drop_column("content_item", "objective")
