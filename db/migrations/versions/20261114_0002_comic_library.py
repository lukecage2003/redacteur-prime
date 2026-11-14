"""Comic Library : comics, documents, pages et éléments d'import.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def _id() -> sa.Column:  # type: ignore[type-arg]
    return sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False)


def _ts() -> list[sa.Column]:  # type: ignore[type-arg]
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "comic",
        _id(),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("series_title", sa.Text(), nullable=True),
        sa.Column("issue_number", sa.Text(), nullable=True),
        sa.Column("language", sa.Text(), nullable=True),
        sa.Column("expected_page_count", sa.Integer(), nullable=True),
        *_ts(),
        sa.CheckConstraint(
            "expected_page_count IS NULL OR expected_page_count > 0",
            name=op.f("ck_comic_expected_page_count"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_comic")),
    )

    op.create_table(
        "document",
        _id(),
        sa.Column("comic_id", UUID, nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("format", sa.Text(), nullable=True),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'UPLOADED'"), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        *_ts(),
        sa.CheckConstraint("char_length(sha256) = 64", name=op.f("ck_document_sha256")),
        sa.CheckConstraint(
            "format IS NULL OR format IN ('PDF', 'CBZ')", name=op.f("ck_document_format")
        ),
        sa.CheckConstraint(
            "status IN ('UPLOADED', 'VALIDATED', 'COMPLETE', 'INCOMPLETE', 'REJECTED', 'FAILED')",
            name=op.f("ck_document_status"),
        ),
        sa.CheckConstraint(
            "page_count IS NULL OR page_count > 0", name=op.f("ck_document_page_count")
        ),
        sa.ForeignKeyConstraint(
            ["comic_id"], ["comic.id"], name=op.f("fk_document_comic_id_comic"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document")),
        sa.UniqueConstraint("sha256", name=op.f("uq_document_sha256")),
    )
    op.create_index("ix_document_comic_id", "document", ["comic_id"])

    op.create_table(
        "page",
        _id(),
        sa.Column("document_id", UUID, nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'PENDING'"), nullable=False),
        sa.Column("render_key", sa.Text(), nullable=True),
        sa.Column("render_profile", sa.Text(), nullable=True),
        sa.Column("render_sha256", sa.Text(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("byte_size", sa.BigInteger(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("rendered_at", sa.DateTime(timezone=True), nullable=True),
        *_ts(),
        sa.CheckConstraint("number >= 1", name=op.f("ck_page_number")),
        sa.CheckConstraint(
            "status IN ('PENDING', 'RENDERED', 'FAILED')", name=op.f("ck_page_status")
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["document.id"],
            name=op.f("fk_page_document_id_document"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_page")),
        sa.UniqueConstraint("document_id", "number", name=op.f("uq_page_document_id_number")),
    )

    op.create_table(
        "import_item",
        _id(),
        sa.Column("run_id", UUID, nullable=False),
        sa.Column("document_id", UUID, nullable=True),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "outcome IN ('NEW', 'DUPLICATE', 'REJECTED')", name=op.f("ck_import_item_outcome")
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["pipeline_run.id"],
            name=op.f("fk_import_item_run_id_pipeline_run"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["document.id"],
            name=op.f("fk_import_item_document_id_document"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_item")),
    )
    op.create_index("ix_import_item_run_id", "import_item", ["run_id"])


def downgrade() -> None:
    # Réservé au développement et à la CI. Voir docs/operations/migrations.md.
    op.drop_index("ix_import_item_run_id", table_name="import_item")
    op.drop_table("import_item")
    op.drop_table("page")
    op.drop_index("ix_document_comic_id", table_name="document")
    op.drop_table("document")
    op.drop_table("comic")
