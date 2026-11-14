"""Schéma relationnel (source de vérité pour `alembic check`).

Toute évolution passe par une migration versionnée dans `db/migrations/versions/`.
Le schéma complet visé est décrit dans DATA_MODEL.md ; seules les tables
réellement implémentées figurent ici.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Table,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)

RUN_STATUSES = ("PENDING", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED")
STEP_STATUSES = ("PENDING", "RUNNING", "SUCCEEDED", "FAILED", "DEAD")


def _in(values: tuple[str, ...]) -> str:
    return "status IN (" + ", ".join(f"'{v}'" for v in values) + ")"


pipeline_run = Table(
    "pipeline_run",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("kind", Text, nullable=False),
    Column("status", Text, nullable=False, server_default=text("'PENDING'")),
    Column("params", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("finished_at", DateTime(timezone=True)),
    CheckConstraint(_in(RUN_STATUSES), name="status"),
)

pipeline_step = Table(
    "pipeline_step",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column(
        "run_id",
        UUID(as_uuid=True),
        ForeignKey("pipeline_run.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("name", Text, nullable=False),
    # Clé d'idempotence : ré-enfiler la même étape ne crée pas de doublon (reprise sûre).
    Column("idempotency_key", Text, nullable=False, unique=True),
    Column("status", Text, nullable=False, server_default=text("'PENDING'")),
    Column("payload", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("result", JSONB),
    Column("error", Text),
    Column("attempts", Integer, nullable=False, server_default=text("0")),
    Column("max_attempts", Integer, nullable=False, server_default=text("3")),
    Column("available_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("locked_at", DateTime(timezone=True)),
    Column("locked_by", Text),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint(_in(STEP_STATUSES), name="status"),
    CheckConstraint("attempts >= 0 AND max_attempts >= 1", name="attempts"),
    Index("ix_pipeline_step_claim", "status", "available_at"),
    Index("ix_pipeline_step_run_id", "run_id"),
)


# --- Comic Library (phase 2) -------------------------------------------------------------

DOCUMENT_STATUSES = ("UPLOADED", "VALIDATED", "COMPLETE", "INCOMPLETE", "REJECTED", "FAILED")
PAGE_STATUSES = ("PENDING", "RENDERED", "FAILED")
IMPORT_OUTCOMES = ("NEW", "DUPLICATE", "REJECTED")


def _ts() -> list[Column[object]]:
    return [
        Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
        Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    ]


comic = Table(
    "comic",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("title", Text, nullable=False),
    Column("series_title", Text),
    Column("issue_number", Text),
    Column("language", Text),
    # Nombre de pages attendu (si connu) : un document plus court ne sera jamais COMPLETE.
    Column("expected_page_count", Integer),
    *_ts(),
    CheckConstraint(
        "expected_page_count IS NULL OR expected_page_count > 0", name="expected_page_count"
    ),
)

document = Table(
    "document",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column(
        "comic_id", UUID(as_uuid=True), ForeignKey("comic.id", ondelete="RESTRICT"), nullable=False
    ),
    Column("sha256", Text, nullable=False, unique=True),
    Column("format", Text),
    Column("byte_size", BigInteger, nullable=False),
    Column("storage_key", Text, nullable=False),
    Column("original_filename", Text, nullable=False),
    Column("page_count", Integer),
    Column("status", Text, nullable=False, server_default=text("'UPLOADED'")),
    Column("error", Text),
    *_ts(),
    CheckConstraint("char_length(sha256) = 64", name="sha256"),
    CheckConstraint("format IS NULL OR format IN ('PDF', 'CBZ')", name="format"),
    CheckConstraint(_in(DOCUMENT_STATUSES), name="status"),
    CheckConstraint("page_count IS NULL OR page_count > 0", name="page_count"),
    Index("ix_document_comic_id", "comic_id"),
)

page = Table(
    "page",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column(
        "document_id",
        UUID(as_uuid=True),
        ForeignKey("document.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("number", Integer, nullable=False),
    Column("status", Text, nullable=False, server_default=text("'PENDING'")),
    Column("render_key", Text),
    Column("render_profile", Text),
    Column("render_sha256", Text),
    Column("width", Integer),
    Column("height", Integer),
    Column("byte_size", BigInteger),
    Column("error", Text),
    Column("rendered_at", DateTime(timezone=True)),
    *_ts(),
    CheckConstraint("number >= 1", name="number"),
    CheckConstraint(_in(PAGE_STATUSES), name="status"),
    UniqueConstraint("document_id", "number"),
)

import_item = Table(
    "import_item",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column(
        "run_id",
        UUID(as_uuid=True),
        ForeignKey("pipeline_run.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("document_id", UUID(as_uuid=True), ForeignKey("document.id", ondelete="RESTRICT")),
    Column("original_filename", Text, nullable=False),
    Column("outcome", Text, nullable=False),
    Column("error", Text),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("outcome IN ('NEW', 'DUPLICATE', 'REJECTED')", name="outcome"),
    Index("ix_import_item_run_id", "run_id"),
)
