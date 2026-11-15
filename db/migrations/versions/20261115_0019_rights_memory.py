"""Droits et mémoire éditoriale : registre des droits et sources, leçons prouvées.

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def _fk(table: str, column: str, target: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], [f"{target}.id"], name=op.f(f"fk_{table}_{column}_{target}"), ondelete="RESTRICT"
    )


def _base() -> list[sa.Column]:  # type: ignore[type-arg]
    return [
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("brand_id", UUID, nullable=False),
    ]


def _created() -> sa.Column:  # type: ignore[type-arg]
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "rights_record",
        *_base(),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("script_id", UUID, nullable=True),
        sa.Column("document_title", sa.Text(), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("panel_number", sa.Integer(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("basis", sa.Text(), nullable=False),
        sa.Column("license", sa.Text(), nullable=True),
        sa.Column("proof", sa.Text(), nullable=False),
        sa.Column("limits", sa.Text(), nullable=False),
        sa.Column("expires_on", sa.Date(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'ACTIVE'"), nullable=False),
        sa.Column("recorded_by", sa.Text(), nullable=False),
        _created(),
        sa.CheckConstraint(
            "kind IN ('PANEL_QUOTE', 'IMAGE', 'MUSIC', 'VOICE', 'VIDEO', 'TEXT')",
            name=op.f("ck_rights_record_kind"),
        ),
        sa.CheckConstraint(
            "basis IN ('QUOTATION', 'LICENSE', 'PERMISSION', 'OWN_WORK', 'PUBLIC_DOMAIN')",
            name=op.f("ck_rights_record_basis"),
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'WITHDRAWN')", name=op.f("ck_rights_record_status")
        ),
        sa.CheckConstraint(
            "kind <> 'PANEL_QUOTE' OR (page_number IS NOT NULL AND panel_number IS NOT NULL)",
            name=op.f("ck_rights_record_panel"),
        ),
        _fk("rights_record", "brand_id", "media_brand"),
        _fk("rights_record", "script_id", "script"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rights_record")),
    )
    op.create_table(
        "editorial_lesson",
        *_base(),
        sa.Column("series_id", UUID, nullable=True),
        sa.Column("lesson", sa.Text(), nullable=False),
        sa.Column("evidence_level", sa.Text(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_id", UUID, nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'ACTIVE'"), nullable=False),
        sa.Column("recorded_by", sa.Text(), nullable=False),
        sa.Column("retracted_reason", sa.Text(), nullable=True),
        _created(),
        sa.CheckConstraint(
            "evidence_level IN ('OBSERVED', 'DEMONSTRATED')",
            name=op.f("ck_editorial_lesson_evidence_level"),
        ),
        sa.CheckConstraint(
            "source_type IN ('content_item', 'experiment')",
            name=op.f("ck_editorial_lesson_source_type"),
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'RETRACTED')", name=op.f("ck_editorial_lesson_status")
        ),
        _fk("editorial_lesson", "brand_id", "media_brand"),
        _fk("editorial_lesson", "series_id", "series"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_editorial_lesson")),
    )


def downgrade() -> None:
    # Réservé au développement et à la CI. Voir docs/operations/migrations.md.
    op.drop_table("editorial_lesson")
    op.drop_table("rights_record")
