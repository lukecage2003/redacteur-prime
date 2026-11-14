"""Maximum Storytelling : scripts (13 étapes), versions, notes sur 100 avec veto, journal.

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()
STEPS = (
    "BRIEF", "RESEARCH", "ANGLE", "HOOK", "STRUCTURE", "OUTLINE", "DRAFT", "FACT_CHECK",
    "REWRITE", "ORALITY", "CRITIQUE", "ADAPTATION", "FINAL_VALIDATION",
)  # fmt: skip


def _id() -> sa.Column:  # type: ignore[type-arg]
    return sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False)


def _now(name: str) -> sa.Column:  # type: ignore[type-arg]
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def _fk(table: str, column: str, target: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], [f"{target}.id"], name=op.f(f"fk_{table}_{column}_{target}"), ondelete="RESTRICT"
    )


def upgrade() -> None:
    steps = ", ".join(f"'{s}'" for s in STEPS)
    op.create_table(
        "script",
        _id(),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("document_ids", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("step", sa.Text(), server_default=sa.text("'BRIEF'"), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'IN_PROGRESS'"), nullable=False),
        sa.Column("adapted_from", UUID, nullable=True),
        sa.Column("author", sa.Text(), nullable=False),
        _now("created_at"),
        _now("updated_at"),
        sa.CheckConstraint("language IN ('fr', 'en')", name=op.f("ck_script_language")),
        sa.CheckConstraint(f"step IN ({steps})", name=op.f("ck_script_step")),
        sa.CheckConstraint("status IN ('IN_PROGRESS', 'VALIDATED')", name=op.f("ck_script_status")),
        _fk("script", "adapted_from", "script"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_script")),
    )
    op.create_table(
        "script_version",
        _id(),
        sa.Column("script_id", UUID, nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("step", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("origin", sa.Text(), nullable=False),
        sa.Column("author", sa.Text(), nullable=False),
        _now("created_at"),
        sa.CheckConstraint(
            "origin IN ('HUMAN', 'IMPORT', 'MODEL')", name=op.f("ck_script_version_origin")
        ),
        _fk("script_version", "script_id", "script"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_script_version")),
        sa.UniqueConstraint("script_id", "number", name=op.f("uq_script_version_script_id_number")),
    )
    op.create_table(
        "script_score",
        _id(),
        sa.Column("version_id", UUID, nullable=False),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column("criteria", JSONB, nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("factual_veto", sa.Boolean(), nullable=False),
        sa.Column("analysis", JSONB, nullable=False),
        _now("created_at"),
        sa.CheckConstraint("total >= 0 AND total <= 100", name=op.f("ck_script_score_total")),
        _fk("script_score", "version_id", "script_version"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_script_score")),
    )
    op.create_index("ix_script_score_version_id", "script_score", ["version_id"])
    op.create_table(
        "script_event",
        _id(),
        sa.Column("script_id", UUID, nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("detail", JSONB, nullable=True),
        sa.Column("author", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        _now("created_at"),
        _fk("script_event", "script_id", "script"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_script_event")),
    )
    op.create_index("ix_script_event_script_id", "script_event", ["script_id"])


def downgrade() -> None:
    # Réservé au développement et à la CI. Voir docs/operations/migrations.md.
    op.drop_index("ix_script_event_script_id", table_name="script_event")
    op.drop_table("script_event")
    op.drop_index("ix_script_score_version_id", table_name="script_score")
    op.drop_table("script_score")
    op.drop_table("script_version")
    op.drop_table("script")
