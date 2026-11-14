"""Comic Vision : analyses de page, cases et zones de texte (ajout seul).

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def _id() -> sa.Column:  # type: ignore[type-arg]
    return sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False)


def _bbox() -> list[sa.Column]:  # type: ignore[type-arg]
    return [sa.Column(n, sa.Float(), nullable=False) for n in ("x", "y", "width", "height")]


def upgrade() -> None:
    op.create_table(
        "page_analysis",
        _id(),
        sa.Column("page_id", UUID, nullable=False),
        sa.Column("run_id", UUID, nullable=True),
        sa.Column("render_sha256", sa.Text(), nullable=False),
        sa.Column("analysis_key", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("detector", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("reading_direction", sa.Text(), nullable=False),
        sa.Column("cost_usd", sa.Numeric(12, 6), server_default=sa.text("0"), nullable=False),
        sa.Column("input_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('SUCCEEDED', 'FAILED')", name=op.f("ck_page_analysis_status")
        ),
        sa.CheckConstraint(
            "reading_direction IN ('LTR', 'RTL')", name=op.f("ck_page_analysis_reading_direction")
        ),
        sa.CheckConstraint("cost_usd >= 0", name=op.f("ck_page_analysis_cost_usd")),
        sa.ForeignKeyConstraint(
            ["page_id"],
            ["page.id"],
            name=op.f("fk_page_analysis_page_id_page"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["pipeline_run.id"],
            name=op.f("fk_page_analysis_run_id_pipeline_run"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_page_analysis")),
        sa.UniqueConstraint("analysis_key", name=op.f("uq_page_analysis_analysis_key")),
    )
    op.create_index("ix_page_analysis_page_id", "page_analysis", ["page_id"])
    op.create_index("ix_page_analysis_run_id", "page_analysis", ["run_id"])
    op.create_index("ix_page_analysis_render_sha256", "page_analysis", ["render_sha256"])

    op.create_table(
        "panel",
        _id(),
        sa.Column("analysis_id", UUID, nullable=False),
        sa.Column("index", sa.Integer(), nullable=False),
        *_bbox(),
        sa.CheckConstraint('"index" >= 1', name=op.f("ck_panel_index")),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["page_analysis.id"],
            name=op.f("fk_panel_analysis_id_page_analysis"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_panel")),
        sa.UniqueConstraint("analysis_id", "index", name=op.f("uq_panel_analysis_id_index")),
    )

    op.create_table(
        "text_region",
        _id(),
        sa.Column("analysis_id", UUID, nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("panel_index", sa.Integer(), nullable=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("speaker", sa.Text(), nullable=True),
        sa.Column("speaker_confidence", sa.Float(), nullable=True),
        *_bbox(),
        sa.CheckConstraint(
            "kind IN ('DIALOGUE', 'THOUGHT', 'NARRATION', 'SFX', 'CAPTION', 'OTHER')",
            name=op.f("ck_text_region_kind"),
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name=op.f("ck_text_region_confidence")
        ),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["page_analysis.id"],
            name=op.f("fk_text_region_analysis_id_page_analysis"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_text_region")),
        sa.UniqueConstraint("analysis_id", "order", name=op.f("uq_text_region_analysis_id_order")),
    )


def downgrade() -> None:
    # Réservé au développement et à la CI. Voir docs/operations/migrations.md.
    op.drop_table("text_region")
    op.drop_table("panel")
    op.drop_index("ix_page_analysis_render_sha256", table_name="page_analysis")
    op.drop_index("ix_page_analysis_run_id", table_name="page_analysis")
    op.drop_index("ix_page_analysis_page_id", table_name="page_analysis")
    op.drop_table("page_analysis")
