"""Research et Theory Laboratory : théories, preuves et contre-preuves, alternatives, journal.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()


def _id() -> sa.Column:  # type: ignore[type-arg]
    return sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False)


def _now(name: str) -> sa.Column:  # type: ignore[type-arg]
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def _theory_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["theory_id"], ["theory.id"], name=op.f(f"fk_{table}_theory_id_theory"), ondelete="RESTRICT"
    )


def upgrade() -> None:
    op.create_table(
        "theory",
        _id(),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column("level", sa.Text(), server_default=sa.text("'SPECULATION'"), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'OPEN'"), nullable=False),
        sa.Column("confidence", sa.Float(), server_default=sa.text("0"), nullable=False),
        sa.Column("document_ids", JSONB, nullable=False),
        sa.Column("subjects", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("counter_search_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("author", sa.Text(), nullable=False),
        _now("created_at"),
        _now("updated_at"),
        sa.CheckConstraint("level IN ('THEORY', 'SPECULATION')", name=op.f("ck_theory_level")),
        sa.CheckConstraint(
            "status IN ('OPEN', 'SUPPORTED', 'CONTESTED', 'REFUTED')", name=op.f("ck_theory_status")
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name=op.f("ck_theory_confidence")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_theory")),
    )
    op.create_table(
        "theory_evidence",
        _id(),
        sa.Column("theory_id", UUID, nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("document_id", UUID, nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("panel_index", sa.Integer(), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column("level", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("origin", sa.Text(), nullable=False),
        sa.Column("added_by", sa.Text(), nullable=False),
        _now("created_at"),
        sa.Column("retracted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retraction_reason", sa.Text(), nullable=True),
        sa.CheckConstraint("role IN ('SUPPORTS', 'REFUTES')", name=op.f("ck_theory_evidence_role")),
        sa.CheckConstraint(
            "level IN ('CANON', 'INTERPRETATION', 'SPECULATION')",
            name=op.f("ck_theory_evidence_level"),
        ),
        sa.CheckConstraint(
            "origin IN ('HUMAN', 'RESEARCHER')", name=op.f("ck_theory_evidence_origin")
        ),
        sa.CheckConstraint("page_number >= 1", name=op.f("ck_theory_evidence_page_number")),
        _theory_fk("theory_evidence"),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["document.id"],
            name=op.f("fk_theory_evidence_document_id_document"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_theory_evidence")),
    )
    op.create_index("ix_theory_evidence_theory_id", "theory_evidence", ["theory_id"])
    op.create_table(
        "theory_alternative",
        _id(),
        sa.Column("theory_id", UUID, nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("author", sa.Text(), nullable=False),
        _now("created_at"),
        _theory_fk("theory_alternative"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_theory_alternative")),
    )
    op.create_index("ix_theory_alternative_theory_id", "theory_alternative", ["theory_id"])
    op.create_table(
        "theory_event",
        _id(),
        sa.Column("theory_id", UUID, nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("detail", JSONB, nullable=True),
        sa.Column("author", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        _now("created_at"),
        _theory_fk("theory_event"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_theory_event")),
    )
    op.create_index("ix_theory_event_theory_id", "theory_event", ["theory_id"])


def downgrade() -> None:
    # Réservé au développement et à la CI. Voir docs/operations/migrations.md.
    op.drop_index("ix_theory_event_theory_id", table_name="theory_event")
    op.drop_table("theory_event")
    op.drop_index("ix_theory_alternative_theory_id", table_name="theory_alternative")
    op.drop_table("theory_alternative")
    op.drop_index("ix_theory_evidence_theory_id", table_name="theory_evidence")
    op.drop_table("theory_evidence")
    op.drop_table("theory")
