"""Forensic Intelligence : observations et références de preuve (ajout seul).

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
KINDS = "'LETTERING', 'SPEECH', 'MENTION', 'CLAIM', 'FIRST_APPEARANCE', 'ALIAS_CANDIDATE', 'CONTRADICTION_CANDIDATE'"


def upgrade() -> None:
    op.create_table(
        "observation",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("run_id", UUID, nullable=True),
        sa.Column("observation_key", sa.Text(), nullable=False),
        sa.Column("extractor", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("level", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("predicate", sa.Text(), nullable=True),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(f"kind IN ({KINDS})", name=op.f("ck_observation_kind")),
        sa.CheckConstraint(
            "level IN ('CANON', 'INTERPRETATION', 'THEORY', 'SPECULATION')",
            name=op.f("ck_observation_level"),
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name=op.f("ck_observation_confidence")
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["pipeline_run.id"],
            name=op.f("fk_observation_run_id_pipeline_run"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_observation")),
        sa.UniqueConstraint("observation_key", name=op.f("uq_observation_observation_key")),
    )
    op.create_index("ix_observation_kind", "observation", ["kind"])
    op.create_index("ix_observation_subject", "observation", ["subject"])

    op.create_table(
        "evidence_ref",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("observation_id", UUID, nullable=False),
        sa.Column("document_id", UUID, nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("panel_index", sa.Integer(), nullable=True),
        sa.Column("analysis_id", UUID, nullable=True),
        sa.Column("text_region_id", UUID, nullable=True),
        sa.Column("x", sa.Float(), nullable=True),
        sa.Column("y", sa.Float(), nullable=True),
        sa.Column("width", sa.Float(), nullable=True),
        sa.Column("height", sa.Float(), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("role", sa.Text(), server_default=sa.text("'SUPPORTS'"), nullable=False),
        sa.CheckConstraint("page_number >= 1", name=op.f("ck_evidence_ref_page_number")),
        sa.CheckConstraint("role IN ('SUPPORTS', 'REFUTES')", name=op.f("ck_evidence_ref_role")),
        sa.ForeignKeyConstraint(
            ["observation_id"],
            ["observation.id"],
            name=op.f("fk_evidence_ref_observation_id_observation"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["document.id"],
            name=op.f("fk_evidence_ref_document_id_document"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["page_analysis.id"],
            name=op.f("fk_evidence_ref_analysis_id_page_analysis"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["text_region_id"],
            ["text_region.id"],
            name=op.f("fk_evidence_ref_text_region_id_text_region"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evidence_ref")),
    )
    op.create_index("ix_evidence_ref_observation_id", "evidence_ref", ["observation_id"])
    op.create_index("ix_evidence_ref_document_id", "evidence_ref", ["document_id"])
    op.create_index("ix_evidence_ref_analysis_id", "evidence_ref", ["analysis_id"])


def downgrade() -> None:
    # Réservé au développement et à la CI. Voir docs/operations/migrations.md.
    op.drop_index("ix_evidence_ref_analysis_id", table_name="evidence_ref")
    op.drop_index("ix_evidence_ref_document_id", table_name="evidence_ref")
    op.drop_index("ix_evidence_ref_observation_id", table_name="evidence_ref")
    op.drop_table("evidence_ref")
    op.drop_index("ix_observation_subject", table_name="observation")
    op.drop_index("ix_observation_kind", table_name="observation")
    op.drop_table("observation")
