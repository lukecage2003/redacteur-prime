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
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
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


def _in(values: tuple[str, ...], column: str = "status") -> str:
    return f"{column} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


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


# --- Comic Vision (phase 3) ---------------------------------------------------------------
# Analyses en ajout seul : une nouvelle version (détecteur, fournisseur, modèle, prompt)
# crée une nouvelle analyse sans effacer les précédentes.

ANALYSIS_STATUSES = ("SUCCEEDED", "FAILED")
TEXT_KINDS = ("DIALOGUE", "THOUGHT", "NARRATION", "SFX", "CAPTION", "OTHER")


def _bbox_columns() -> list[Column[object]]:
    return [Column(name, Float, nullable=False) for name in ("x", "y", "width", "height")]


page_analysis = Table(
    "page_analysis",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column(
        "page_id", UUID(as_uuid=True), ForeignKey("page.id", ondelete="RESTRICT"), nullable=False
    ),
    Column("run_id", UUID(as_uuid=True), ForeignKey("pipeline_run.id", ondelete="RESTRICT")),
    # Empreinte de l'image analysée : une analyse vaut pour toute page au rendu identique.
    Column("render_sha256", Text, nullable=False),
    # (rendu, détecteur, fournisseur, modèle, prompt) : jamais deux fois la même analyse payée.
    Column("analysis_key", Text, nullable=False, unique=True),
    Column("status", Text, nullable=False),
    Column("detector", Text, nullable=False),
    Column("provider", Text, nullable=False),
    Column("model", Text, nullable=False),
    Column("prompt_version", Text, nullable=False),
    Column("reading_direction", Text, nullable=False),
    Column("cost_usd", Numeric(12, 6), nullable=False, server_default=text("0")),
    Column("input_tokens", Integer, nullable=False, server_default=text("0")),
    Column("output_tokens", Integer, nullable=False, server_default=text("0")),
    Column("latency_ms", Float),
    Column("error", Text),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint(_in(ANALYSIS_STATUSES), name="status"),
    CheckConstraint("reading_direction IN ('LTR', 'RTL')", name="reading_direction"),
    CheckConstraint("cost_usd >= 0", name="cost_usd"),
    Index("ix_page_analysis_page_id", "page_id"),
    Index("ix_page_analysis_run_id", "run_id"),
    Index("ix_page_analysis_render_sha256", "render_sha256"),
)

panel = Table(
    "panel",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column(
        "analysis_id",
        UUID(as_uuid=True),
        ForeignKey("page_analysis.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("index", Integer, nullable=False),
    *_bbox_columns(),
    CheckConstraint('"index" >= 1', name="index"),
    UniqueConstraint("analysis_id", "index"),
)

text_region = Table(
    "text_region",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column(
        "analysis_id",
        UUID(as_uuid=True),
        ForeignKey("page_analysis.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("order", Integer, nullable=False),
    Column("panel_index", Integer),
    Column("kind", Text, nullable=False),
    Column("text", Text, nullable=False),
    Column("language", Text),
    Column("confidence", Float, nullable=False),
    Column("speaker", Text),
    Column("speaker_confidence", Float),
    *_bbox_columns(),
    CheckConstraint(_in(TEXT_KINDS, "kind"), name="kind"),
    CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence"),
    UniqueConstraint("analysis_id", "order"),
)
