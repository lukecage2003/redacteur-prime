"""Schéma relationnel (source de vérité pour `alembic check`).

Toute évolution passe par une migration versionnée dans `db/migrations/versions/`.
Le schéma complet visé est décrit dans DATA_MODEL.md ; seules les tables
réellement implémentées figurent ici.
"""

from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
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


# --- Forensic Intelligence (phase 4) ------------------------------------------------------

OBSERVATION_KINDS = (
    "LETTERING",
    "SPEECH",
    "MENTION",
    "CLAIM",
    "FIRST_APPEARANCE",
    "ALIAS_CANDIDATE",
    "CONTRADICTION_CANDIDATE",
)
EVIDENCE_LEVELS = ("CANON", "INTERPRETATION", "THEORY", "SPECULATION")

observation = Table(
    "observation",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("run_id", UUID(as_uuid=True), ForeignKey("pipeline_run.id", ondelete="RESTRICT")),
    # Empreinte stable (extracteur + contenu + preuves) : ré-exécuter ne duplique rien.
    Column("observation_key", Text, nullable=False, unique=True),
    Column("extractor", Text, nullable=False),
    Column("kind", Text, nullable=False),
    Column("level", Text, nullable=False),
    Column("subject", Text),
    Column("predicate", Text),
    Column("value", Text),
    Column("statement", Text, nullable=False),
    Column("confidence", Float, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint(_in(OBSERVATION_KINDS, "kind"), name="kind"),
    CheckConstraint(_in(EVIDENCE_LEVELS, "level"), name="level"),
    CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence"),
    Index("ix_observation_kind", "kind"),
    Index("ix_observation_subject", "subject"),
)

evidence_ref = Table(
    "evidence_ref",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column(
        "observation_id",
        UUID(as_uuid=True),
        ForeignKey("observation.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "document_id",
        UUID(as_uuid=True),
        ForeignKey("document.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("page_number", Integer, nullable=False),
    Column("panel_index", Integer),
    Column("analysis_id", UUID(as_uuid=True), ForeignKey("page_analysis.id", ondelete="RESTRICT")),
    Column("text_region_id", UUID(as_uuid=True), ForeignKey("text_region.id", ondelete="RESTRICT")),
    Column("x", Float),
    Column("y", Float),
    Column("width", Float),
    Column("height", Float),
    Column("excerpt", Text),
    Column("role", Text, nullable=False, server_default=text("'SUPPORTS'")),
    CheckConstraint("page_number >= 1", name="page_number"),
    CheckConstraint("role IN ('SUPPORTS', 'REFUTES')", name="role"),
    Index("ix_evidence_ref_observation_id", "observation_id"),
    Index("ix_evidence_ref_document_id", "document_id"),
    Index("ix_evidence_ref_analysis_id", "analysis_id"),
)


# --- Knowledge Intelligence (phase 5) -----------------------------------------------------

ENTITY_TYPES = (
    "CHARACTER",
    "EVENT",
    "LOCATION",
    "OBJECT",
    "CONCEPT",
    "SERIES",
    "CONTINUITY",
    "COMIC",
)
RELATION_TYPES = (
    "APPEARS_IN",
    "REFERENCES",
    "CONTRADICTS",
    "PRECEDES",
    "REVEALS",
    "FORESHADOWS",
    "RELATED_TO",
    "OPPOSES",
)

entity = Table(
    "entity",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("type", Text, nullable=False),
    Column("canonical_name", Text, nullable=False),
    Column("folded_name", Text, nullable=False),
    Column("description", Text),
    # Fusion (correction humaine) : l'entité absorbée est conservée et pointe vers la cible.
    Column("merged_into", UUID(as_uuid=True), ForeignKey("entity.id", ondelete="RESTRICT")),
    *_ts(),
    CheckConstraint(_in(ENTITY_TYPES, "type"), name="type"),
    Index("ix_entity_type_folded_name", "type", "folded_name"),
)

entity_alias = Table(
    "entity_alias",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column(
        "entity_id",
        UUID(as_uuid=True),
        ForeignKey("entity.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("alias", Text, nullable=False),
    Column("folded", Text, nullable=False),
    Column("language", Text),
    Column("origin", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("origin IN ('EXTRACTOR', 'HUMAN')", name="origin"),
    UniqueConstraint("entity_id", "folded"),
    Index("ix_entity_alias_folded", "folded"),
)

relation = Table(
    "relation",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("relation_key", Text, nullable=False, unique=True),
    Column(
        "source_id",
        UUID(as_uuid=True),
        ForeignKey("entity.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "target_id",
        UUID(as_uuid=True),
        ForeignKey("entity.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("type", Text, nullable=False),
    Column("qualifier", Text),
    Column("level", Text, nullable=False),
    Column("confidence", Float, nullable=False),
    Column("origin", Text, nullable=False),
    # Retrait (correction humaine) : la relation reste en base, marquée retirée.
    Column("retracted_at", DateTime(timezone=True)),
    *_ts(),
    CheckConstraint(_in(RELATION_TYPES, "type"), name="type"),
    CheckConstraint(_in(EVIDENCE_LEVELS, "level"), name="level"),
    CheckConstraint("origin IN ('EXTRACTOR', 'HUMAN')", name="origin"),
    CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence"),
    CheckConstraint("source_id <> target_id", name="not_self"),
    Index("ix_relation_source_id", "source_id"),
    Index("ix_relation_target_id", "target_id"),
)

relation_evidence = Table(
    "relation_evidence",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column(
        "relation_id",
        UUID(as_uuid=True),
        ForeignKey("relation.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("observation_id", UUID(as_uuid=True), ForeignKey("observation.id", ondelete="RESTRICT")),
    Column(
        "document_id",
        UUID(as_uuid=True),
        ForeignKey("document.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("page_number", Integer, nullable=False),
    Column("panel_index", Integer),
    Column("excerpt", Text),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("page_number >= 1", name="page_number"),
    UniqueConstraint("relation_id", "observation_id"),
    Index("ix_relation_evidence_relation_id", "relation_id"),
)

correction = Table(
    "correction",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("target_type", Text, nullable=False),
    Column("target_id", UUID(as_uuid=True), nullable=False),
    Column("action", Text, nullable=False),
    Column("before", JSONB),
    Column("after", JSONB),
    Column("author", Text, nullable=False),
    Column("reason", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("target_type IN ('ENTITY', 'RELATION')", name="target_type"),
    Index("ix_correction_target_id", "target_id"),
)

search_document = Table(
    "search_document",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("kind", Text, nullable=False),
    Column("ref_id", UUID(as_uuid=True), nullable=False),
    Column("document_id", UUID(as_uuid=True), ForeignKey("document.id", ondelete="RESTRICT")),
    Column("page_number", Integer),
    Column("panel_index", Integer),
    Column("content", Text, nullable=False),
    Column("folded", Text, nullable=False),
    Column("embedder", Text, nullable=False),
    Column("embedding", Vector(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("kind IN ('TEXT', 'ENTITY')", name="kind"),
    UniqueConstraint("kind", "ref_id", "embedder"),
    Index("ix_search_document_document_id", "document_id"),
)


# --- Editorial Director (phase 6) -----------------------------------------------------------

MISSION_STATUSES = ("PLANNED", "RUNNING", "AWAITING_APPROVAL", "APPROVED", "REJECTED", "FAILED")
TASK_STATUSES = ("PENDING", "RUNNING", "SUCCEEDED", "FAILED", "SKIPPED")

mission = Table(
    "mission",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("brand_id", UUID(as_uuid=True), ForeignKey("media_brand.id", ondelete="RESTRICT")),
    Column("type", Text, nullable=False),
    Column("title", Text, nullable=False),
    Column("status", Text, nullable=False, server_default=text("'PLANNED'")),
    Column("document_ids", JSONB, nullable=False),
    Column("params", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("result", JSONB),
    Column("error", Text),
    Column("run_id", UUID(as_uuid=True), ForeignKey("pipeline_run.id", ondelete="RESTRICT")),
    *_ts(),
    Column("completed_at", DateTime(timezone=True)),
    CheckConstraint(_in(MISSION_STATUSES), name="status"),
)

mission_task = Table(
    "mission_task",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column(
        "mission_id",
        UUID(as_uuid=True),
        ForeignKey("mission.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("position", Integer, nullable=False),
    Column("key", Text, nullable=False),
    Column("agent", Text, nullable=False),
    Column("critical", Boolean, nullable=False),
    Column("status", Text, nullable=False, server_default=text("'PENDING'")),
    Column("input", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("output", JSONB),
    Column("error", Text),
    Column("attempts", Integer, nullable=False, server_default=text("0")),
    Column("started_at", DateTime(timezone=True)),
    Column("finished_at", DateTime(timezone=True)),
    CheckConstraint(_in(TASK_STATUSES), name="status"),
    UniqueConstraint("mission_id", "position"),
)

approval_request = Table(
    "approval_request",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column(
        "mission_id",
        UUID(as_uuid=True),
        ForeignKey("mission.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("kind", Text, nullable=False),
    Column("summary", Text, nullable=False),
    Column("recommendation", Text, nullable=False),
    Column("status", Text, nullable=False, server_default=text("'PENDING'")),
    Column("decided_by", Text),
    Column("comment", Text),
    Column("decided_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("status IN ('PENDING', 'APPROVED', 'REJECTED')", name="status"),
    Index("ix_approval_request_mission_id", "mission_id"),
)

agent_run = Table(
    "agent_run",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column(
        "mission_task_id",
        UUID(as_uuid=True),
        ForeignKey("mission_task.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("agent", Text, nullable=False),
    Column("provider", Text),
    Column("model", Text),
    Column("prompt_id", Text),
    Column("prompt_version", Text),
    Column("input_tokens", Integer, nullable=False, server_default=text("0")),
    Column("output_tokens", Integer, nullable=False, server_default=text("0")),
    Column("cost_usd", Numeric(12, 6), nullable=False, server_default=text("0")),
    Column("latency_ms", Float),
    Column("error", Text),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Index("ix_agent_run_mission_task_id", "mission_task_id"),
)


# --- Research et Theory Laboratory (phase 7) ---------------------------------------------
# Une théorie n'est jamais CANON (contrainte en base). Rien n'est effacé : une preuve est
# retirée (datée, motivée) et chaque changement est journalisé dans `theory_event`.

THEORY_STATUSES = ("OPEN", "SUPPORTED", "CONTESTED", "REFUTED")


def _theory_fk() -> Column[object]:
    return Column(
        "theory_id",
        UUID(as_uuid=True),
        ForeignKey("theory.id", ondelete="RESTRICT"),
        nullable=False,
    )


theory = Table(
    "theory",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("title", Text, nullable=False),
    Column("claim", Text, nullable=False),
    Column("level", Text, nullable=False, server_default=text("'SPECULATION'")),
    Column("status", Text, nullable=False, server_default=text("'OPEN'")),
    Column("confidence", Float, nullable=False, server_default=text("0")),
    Column("document_ids", JSONB, nullable=False),
    Column("subjects", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("counter_search_at", DateTime(timezone=True)),
    Column("author", Text, nullable=False),
    *_ts(),
    CheckConstraint("level IN ('THEORY', 'SPECULATION')", name="level"),
    CheckConstraint(_in(THEORY_STATUSES), name="status"),
    CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence"),
)

theory_evidence = Table(
    "theory_evidence",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    _theory_fk(),
    Column("role", Text, nullable=False),
    Column(
        "document_id",
        UUID(as_uuid=True),
        ForeignKey("document.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("page_number", Integer, nullable=False),
    Column("panel_index", Integer),
    Column("excerpt", Text),
    Column("verified", Boolean, nullable=False),
    Column("level", Text, nullable=False),
    Column("note", Text),
    Column("origin", Text, nullable=False),
    Column("added_by", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("retracted_at", DateTime(timezone=True)),
    Column("retraction_reason", Text),
    CheckConstraint("role IN ('SUPPORTS', 'REFUTES')", name="role"),
    CheckConstraint("level IN ('CANON', 'INTERPRETATION', 'SPECULATION')", name="level"),
    CheckConstraint("origin IN ('HUMAN', 'RESEARCHER')", name="origin"),
    CheckConstraint("page_number >= 1", name="page_number"),
    Index("ix_theory_evidence_theory_id", "theory_id"),
)

theory_alternative = Table(
    "theory_alternative",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    _theory_fk(),
    Column("text", Text, nullable=False),
    Column("author", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Index("ix_theory_alternative_theory_id", "theory_id"),
)

theory_event = Table(
    "theory_event",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    _theory_fk(),
    Column("action", Text, nullable=False),
    Column("detail", JSONB),
    Column("author", Text, nullable=False),
    Column("reason", Text),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Index("ix_theory_event_theory_id", "theory_id"),
)


# --- Market Intelligence (phases 2b et 8) --------------------------------------------------
# Uniquement des données PUBLIQUES observées (ou importées avec leur source) : aucune métrique
# privée de concurrent (CTR, rétention, impressions) ne peut être stockée — contrainte en base.

MARKET_PUBLIC_METRICS = ("views", "likes", "comments")

market_source = Table(
    "market_source",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("key", Text, nullable=False, unique=True),
    Column("name", Text, nullable=False),
    Column("kind", Text, nullable=False),
    Column("access", Text, nullable=False),
    Column("quota", Text, nullable=False),
    Column("terms_url", Text, nullable=False),
    Column("data_class", Text, nullable=False),
    Column("language", Text),
    Column("config", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("verified_at", DateTime(timezone=True)),
    Column("verified_by", Text),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("kind IN ('YOUTUBE_API', 'RSS', 'MANUAL')", name="kind"),
    CheckConstraint("data_class IN ('PUBLIC', 'ESTIMATE', 'HYPOTHESIS')", name="data_class"),
    CheckConstraint("language IS NULL OR language IN ('fr', 'en')", name="language"),
)

market_collection = Table(
    "market_collection",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column(
        "source_id",
        UUID(as_uuid=True),
        ForeignKey("market_source.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("status", Text, nullable=False),
    Column("params", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("items", Integer, nullable=False, server_default=text("0")),
    Column("metrics", Integer, nullable=False, server_default=text("0")),
    Column("quota_units", Integer, nullable=False, server_default=text("0")),
    Column("error", Text),
    Column("author", Text, nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("finished_at", DateTime(timezone=True)),
    CheckConstraint("status IN ('RUNNING', 'SUCCEEDED', 'FAILED')", name="status"),
    Index("ix_market_collection_source_id", "source_id"),
)

market_item = Table(
    "market_item",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column(
        "source_id",
        UUID(as_uuid=True),
        ForeignKey("market_source.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("platform", Text, nullable=False),
    Column("external_id", Text, nullable=False),
    Column("url", Text),
    Column("title", Text, nullable=False),
    Column("description", Text),
    Column("channel", Text),
    Column("language", Text, nullable=False),
    Column("published_at", DateTime(timezone=True)),
    Column("first_seen_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("platform", "external_id"),
    CheckConstraint("language IN ('fr', 'en')", name="language"),
)

market_metric = Table(
    "market_metric",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column(
        "item_id",
        UUID(as_uuid=True),
        ForeignKey("market_item.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "collection_id",
        UUID(as_uuid=True),
        ForeignKey("market_collection.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("metric", Text, nullable=False),
    Column("value", BigInteger, nullable=False),
    Column("data_class", Text, nullable=False),
    Column("observed_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("item_id", "metric", "observed_at"),
    CheckConstraint(_in(MARKET_PUBLIC_METRICS, "metric"), name="metric"),
    CheckConstraint("data_class = 'PUBLIC'", name="data_class"),
    CheckConstraint("value >= 0", name="value"),
)

market_topic = Table(
    "market_topic",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("name", Text, nullable=False, unique=True),
    Column("keywords_fr", JSONB, nullable=False),
    Column("keywords_en", JSONB, nullable=False),
    Column("author", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)


# --- Maximum Storytelling (phase 10) --------------------------------------------------------

SCRIPT_STEPS = (
    "BRIEF",
    "RESEARCH",
    "ANGLE",
    "HOOK",
    "STRUCTURE",
    "OUTLINE",
    "DRAFT",
    "FACT_CHECK",
    "REWRITE",
    "ORALITY",
    "CRITIQUE",
    "ADAPTATION",
    "FINAL_VALIDATION",
)

script = Table(
    "script",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("brand_id", UUID(as_uuid=True), ForeignKey("media_brand.id", ondelete="RESTRICT")),
    Column("title", Text, nullable=False),
    Column("language", Text, nullable=False),
    Column("document_ids", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("step", Text, nullable=False, server_default=text("'BRIEF'")),
    Column("status", Text, nullable=False, server_default=text("'IN_PROGRESS'")),
    Column("adapted_from", UUID(as_uuid=True), ForeignKey("script.id", ondelete="RESTRICT")),
    # Phase 17 : niveau de connaissance visé et variante d'un même sujet à un autre niveau.
    Column("level", Text),
    Column("level_of", UUID(as_uuid=True), ForeignKey("script.id", ondelete="RESTRICT")),
    Column("author", Text, nullable=False),
    *_ts(),
    CheckConstraint("language IN ('fr', 'en')", name="language"),
    CheckConstraint(
        "level IS NULL OR level IN ('DISCOVERY', 'EXPLORATION', 'EXPERTISE')", name="level"
    ),
    CheckConstraint(_in(SCRIPT_STEPS, "step"), name="step"),
    CheckConstraint("status IN ('IN_PROGRESS', 'VALIDATED')", name="status"),
)

script_version = Table(
    "script_version",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column(
        "script_id",
        UUID(as_uuid=True),
        ForeignKey("script.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("number", Integer, nullable=False),
    Column("step", Text, nullable=False),
    Column("content", Text, nullable=False),
    Column("origin", Text, nullable=False),
    Column("author", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("script_id", "number"),
    CheckConstraint("origin IN ('HUMAN', 'IMPORT', 'MODEL')", name="origin"),
)

script_score = Table(
    "script_score",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column(
        "version_id",
        UUID(as_uuid=True),
        ForeignKey("script_version.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("method", Text, nullable=False),
    Column("criteria", JSONB, nullable=False),
    Column("total", Integer, nullable=False),
    Column("factual_veto", Boolean, nullable=False),
    Column("analysis", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("total >= 0 AND total <= 100", name="total"),
    Index("ix_script_score_version_id", "version_id"),
)

script_event = Table(
    "script_event",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column(
        "script_id",
        UUID(as_uuid=True),
        ForeignKey("script.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("action", Text, nullable=False),
    Column("detail", JSONB),
    Column("author", Text, nullable=False),
    Column("reason", Text),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Index("ix_script_event_script_id", "script_id"),
)


# --- Performance Intelligence (phase 11) ----------------------------------------------------
# Uniquement les contenus PUBLIÉS PAR PRIMESTONE : leurs métriques privées (CTR, rétention…)
# sont des données PRIVATE_AUTHORIZED de la chaîne du propriétaire, jamais d'un concurrent.

PERFORMANCE_METRICS = (
    "views",
    "impressions",
    "ctr",
    "avg_view_duration_s",
    "avg_view_percentage",
    "watch_time_min",
    "likes",
    "comments",
    "subscribers_gained",
    # Phase 14 : mesure élargie (uniquement si la plateforme les fournit, jamais estimées).
    "subscribers_lost",
    "shares",
    "saves",
    "returning_viewers",
    "new_viewers",
    "unique_viewers",
    "engaged_views",
)
CONTENT_OBJECTIVES = ("DISCOVERY", "EXPLORATION", "EXPERTISE", "COMMUNITY")
CONTENT_FORMATS = ("LONG", "SHORT", "REEL", "CAROUSEL", "POST", "PODCAST", "LIVE")
METRIC_DIMENSIONS = ("traffic_source", "country", "age_group", "device", "subscribed_status")

content_item = Table(
    "content_item",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("brand_id", UUID(as_uuid=True), ForeignKey("media_brand.id", ondelete="RESTRICT")),
    Column("platform", Text, nullable=False),
    Column("external_id", Text, nullable=False),
    Column("title", Text, nullable=False),
    Column("url", Text),
    Column("language", Text),
    Column("published_at", DateTime(timezone=True)),
    Column("script_id", UUID(as_uuid=True), ForeignKey("script.id", ondelete="RESTRICT")),
    Column("objective", Text),
    Column("format", Text),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("platform", "external_id"),
    CheckConstraint("language IS NULL OR language IN ('fr', 'en')", name="language"),
    CheckConstraint(
        "objective IS NULL OR " + _in(CONTENT_OBJECTIVES, "objective"), name="objective"
    ),
    CheckConstraint("format IS NULL OR " + _in(CONTENT_FORMATS, "format"), name="format"),
)

performance_metric = Table(
    "performance_metric",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column(
        "content_id",
        UUID(as_uuid=True),
        ForeignKey("content_item.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("metric", Text, nullable=False),
    Column("value", Numeric(18, 4), nullable=False),
    Column("period_start", Date),
    Column("period_end", Date),
    Column("source", Text, nullable=False),
    Column("data_class", Text, nullable=False),
    Column("imported_by", Text, nullable=False),
    Column("observed_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    # Segment AGRÉGÉ fourni par la plateforme (ex. traffic_source = YT_SEARCH) ; NULL = total.
    Column("dimension", Text),
    Column("dimension_value", Text),
    CheckConstraint(_in(PERFORMANCE_METRICS, "metric"), name="metric"),
    CheckConstraint(
        "dimension IS NULL OR " + _in(METRIC_DIMENSIONS, "dimension"), name="dimension"
    ),
    CheckConstraint(
        "source IN ('YOUTUBE_STUDIO_CSV', 'YOUTUBE_ANALYTICS_API', 'MANUAL')", name="source"
    ),
    CheckConstraint("data_class = 'PRIVATE_AUTHORIZED'", name="data_class"),
    CheckConstraint("value >= 0", name="value"),
    Index("ix_performance_metric_content_id", "content_id"),
)


retention_point = Table(
    "retention_point",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column(
        "content_id",
        UUID(as_uuid=True),
        ForeignKey("content_item.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("elapsed_ratio", Numeric(6, 4), nullable=False),
    Column("audience_watch_ratio", Numeric(8, 4), nullable=False),
    Column("relative_performance", Numeric(8, 4)),
    Column("source", Text, nullable=False),
    Column("observed_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("content_id", "elapsed_ratio", "observed_at"),
    CheckConstraint("elapsed_ratio >= 0 AND elapsed_ratio <= 1", name="elapsed_ratio"),
    CheckConstraint("audience_watch_ratio >= 0", name="audience_watch_ratio"),
)

# --- Expérimentation (phase 14) -------------------------------------------------------------

EXPERIMENT_VARIABLES = ("TITLE", "THUMBNAIL", "HOOK", "PROMISE", "FORMAT", "LENGTH", "OTHER")
EXPERIMENT_STATUSES = ("PLANNED", "RUNNING", "CONCLUDED", "INCONCLUSIVE")

experiment = Table(
    "experiment",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("brand_id", UUID(as_uuid=True), ForeignKey("media_brand.id", ondelete="RESTRICT")),
    Column("title", Text, nullable=False),
    Column("hypothesis", Text, nullable=False),
    Column("variable", Text, nullable=False),
    Column("audience", Text),
    Column("format", Text),
    Column("metric", Text, nullable=False),
    Column("content_ids", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("period_start", Date),
    Column("period_end", Date),
    Column("status", Text, nullable=False, server_default=text("'PLANNED'")),
    Column("result", JSONB),
    Column("conclusion", Text),
    Column("next_experiment", Text),
    Column("author", Text, nullable=False),
    *_ts(),
    CheckConstraint(_in(EXPERIMENT_VARIABLES, "variable"), name="variable"),
    CheckConstraint(_in(EXPERIMENT_STATUSES), name="status"),
)

experiment_variant = Table(
    "experiment_variant",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column(
        "experiment_id",
        UUID(as_uuid=True),
        ForeignKey("experiment.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("label", Text, nullable=False),
    Column("description", Text, nullable=False),
    Column("exposures", BigInteger),
    Column("successes", BigInteger),
    Column("reported_share", Numeric(6, 4)),
    Column("source", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("experiment_id", "label"),
    CheckConstraint(
        "exposures IS NULL OR (exposures >= 0 AND successes >= 0 AND successes <= exposures)",
        name="counts",
    ),
    CheckConstraint(
        "reported_share IS NULL OR (reported_share >= 0 AND reported_share <= 1)",
        name="reported_share",
    ),
)


# --- Audience Intelligence & communauté (phase 15) ------------------------------------------
# Segments fondés sur motivations et niveau de connaissance (jamais l'âge). Un segment n'est
# CONFIRMED qu'avec des preuves observées d'au moins deux natures différentes. Aucun
# commentaire ne conserve l'identité de son auteur.

AUDIENCE_KNOWLEDGE_LEVELS = ("NOVICE", "INTERMEDIATE", "EXPERT")
AUDIENCE_EVIDENCE_KINDS = ("METRIC", "COMMENT_CLUSTER", "MARKET", "DECLARED")
AUDIENCE_LINK_TARGETS = ("ENTITY", "TOPIC", "FORMAT", "PLATFORM")
COMMENT_KINDS = ("QUESTION", "THEORY", "REQUEST", "CONTROVERSY", "PRAISE", "OTHER")

audience_segment = Table(
    "audience_segment",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("name", Text, nullable=False, unique=True),
    Column("description", Text, nullable=False),
    Column("motivations", JSONB, nullable=False),
    Column("knowledge_level", Text),
    Column("status", Text, nullable=False, server_default=text("'HYPOTHESIS'")),
    Column("author", Text, nullable=False),
    *_ts(),
    CheckConstraint("status IN ('HYPOTHESIS', 'CONFIRMED')", name="status"),
    CheckConstraint(
        "knowledge_level IS NULL OR " + _in(AUDIENCE_KNOWLEDGE_LEVELS, "knowledge_level"),
        name="knowledge_level",
    ),
    CheckConstraint("jsonb_array_length(motivations) >= 1", name="motivations"),
)

audience_evidence = Table(
    "audience_evidence",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column(
        "segment_id",
        UUID(as_uuid=True),
        ForeignKey("audience_segment.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("kind", Text, nullable=False),
    Column("statement", Text, nullable=False),
    Column("data", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("data_class", Text, nullable=False),
    Column("added_by", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("retracted_at", DateTime(timezone=True)),
    CheckConstraint(_in(AUDIENCE_EVIDENCE_KINDS, "kind"), name="kind"),
    CheckConstraint(
        "data_class IN ('PUBLIC', 'PRIVATE_AUTHORIZED', 'ESTIMATE', 'HYPOTHESIS')",
        name="data_class",
    ),
    Index("ix_audience_evidence_segment_id", "segment_id"),
)

audience_link = Table(
    "audience_link",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column(
        "segment_id",
        UUID(as_uuid=True),
        ForeignKey("audience_segment.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("target_kind", Text, nullable=False),
    Column("target", Text, nullable=False),
    Column("relation", Text, nullable=False),
    Column(
        "evidence_id",
        UUID(as_uuid=True),
        ForeignKey("audience_evidence.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("segment_id", "target_kind", "target", "relation"),
    CheckConstraint(_in(AUDIENCE_LINK_TARGETS, "target_kind"), name="target_kind"),
    CheckConstraint(
        "relation IN ('INTERESTED_IN', 'PREFERS', 'USES', 'ASKS_ABOUT', 'FRUSTRATED_BY')",
        name="relation",
    ),
)

community_comment = Table(
    "community_comment",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("platform", Text, nullable=False),
    Column("external_id", Text, nullable=False),
    Column(
        "content_id",
        UUID(as_uuid=True),
        ForeignKey("content_item.id", ondelete="RESTRICT"),
    ),
    Column("text", Text, nullable=False),
    Column("language", Text),
    Column("kind", Text, nullable=False),
    Column("like_count", Integer, nullable=False, server_default=text("0")),
    Column("published_at", DateTime(timezone=True)),
    Column("fetched_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("platform", "external_id"),
    CheckConstraint(_in(COMMENT_KINDS, "kind"), name="kind"),
)


# --- Creative Intelligence : marque, séries, packaging (phase 18) ---------------------------

brand_charter = Table(
    "brand_charter",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("version", Integer, nullable=False, unique=True),
    Column("name", Text, nullable=False),
    Column("rules", JSONB, nullable=False),
    Column("author", Text, nullable=False),
    Column("note", Text),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    # Phase 20 : règles de marque (« brand guidelines ») rattachées, par langue, approuvées.
    Column("brand_id", UUID(as_uuid=True), ForeignKey("media_brand.id", ondelete="RESTRICT")),
    Column("language", Text),
    Column("status", Text, nullable=False, server_default=text("'APPROVED'")),
    Column("approved_by", Text),
    Column("approved_at", DateTime(timezone=True)),
    CheckConstraint("status IN ('DRAFT', 'APPROVED', 'RETIRED')", name="status"),
    CheckConstraint("language IS NULL OR language IN ('fr', 'en')", name="language"),
)

series = Table(
    "series",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("name", Text, nullable=False, unique=True),
    Column("promise", Text, nullable=False),
    Column("identity", Text, nullable=False),
    Column(
        "segment_id", UUID(as_uuid=True), ForeignKey("audience_segment.id", ondelete="RESTRICT")
    ),
    Column("tone", Text, nullable=False),
    Column("structure", JSONB, nullable=False),
    Column("target_minutes", Integer, nullable=False),
    Column("art_direction", Text, nullable=False),
    Column("distribution", JSONB, nullable=False),
    Column("evolution", Text, nullable=False),
    Column("status", Text, nullable=False, server_default=text("'ACTIVE'")),
    Column("author", Text, nullable=False),
    Column("brand_id", UUID(as_uuid=True), ForeignKey("media_brand.id", ondelete="RESTRICT")),
    *_ts(),
    CheckConstraint("status IN ('ACTIVE', 'PAUSED', 'ENDED')", name="status"),
    CheckConstraint("target_minutes > 0 AND target_minutes <= 240", name="target_minutes"),
)

series_episode = Table(
    "series_episode",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column(
        "series_id",
        UUID(as_uuid=True),
        ForeignKey("series.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "script_id",
        UUID(as_uuid=True),
        ForeignKey("script.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("number", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("series_id", "number"),
    UniqueConstraint("script_id"),
)

packaging_set = Table(
    "packaging_set",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column(
        "script_id",
        UUID(as_uuid=True),
        ForeignKey("script.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("script_version", Integer, nullable=False),
    Column("method", Text, nullable=False),
    Column("charter_version", Integer),
    Column("content", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Index("ix_packaging_set_script_id", "script_id"),
)


# --- Marque et gouvernance (phase 20) -------------------------------------------------------
# PRIMESTONE est une marque média autonome ; le fondateur est directeur éditorial. Les agents
# PROPOSENT ; seules les décisions approuvées s'appliquent ; rien n'est publié automatiquement.

DECISION_STATUSES = ("PROPOSED", "APPROVED", "REJECTED", "SUPERSEDED", "REVERTED")

media_brand = Table(
    "media_brand",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("slug", Text, nullable=False, unique=True),
    Column("name", Text, nullable=False),
    Column("mission", Text, nullable=False),
    Column("languages", JSONB, nullable=False),
    Column("primary_language", Text, nullable=False),
    Column("status", Text, nullable=False, server_default=text("'ACTIVE'")),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("status IN ('ACTIVE', 'ARCHIVED')", name="status"),
    CheckConstraint("primary_language IN ('fr', 'en')", name="primary_language"),
)


def _brand_fk() -> Column[object]:
    return Column("brand_id", UUID(as_uuid=True), ForeignKey("media_brand.id", ondelete="RESTRICT"))


editorial_pillar = Table(
    "editorial_pillar",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column(
        "brand_id",
        UUID(as_uuid=True),
        ForeignKey("media_brand.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("name", Text, nullable=False),
    Column("description", Text, nullable=False),
    Column("rules", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("status", Text, nullable=False, server_default=text("'PROPOSED'")),
    Column("version", Integer, nullable=False, server_default=text("1")),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("brand_id", "name"),
    CheckConstraint("status IN ('PROPOSED', 'ACTIVE', 'RETIRED')", name="status"),
)

editorial_policy = Table(
    "editorial_policy",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column(
        "brand_id",
        UUID(as_uuid=True),
        ForeignKey("media_brand.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("action", Text, nullable=False),
    Column("requires_approval", Boolean, nullable=False),
    Column("approver", Text, nullable=False, server_default=text("'FOUNDER'")),
    Column("note", Text),
    Column("version", Integer, nullable=False, server_default=text("1")),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("brand_id", "action"),
)

editorial_decision = Table(
    "editorial_decision",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column(
        "brand_id",
        UUID(as_uuid=True),
        ForeignKey("media_brand.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("action", Text, nullable=False),
    Column("subject_type", Text, nullable=False),
    Column("subject_id", Text),
    Column("proposal", JSONB, nullable=False),
    Column("status", Text, nullable=False, server_default=text("'PROPOSED'")),
    Column("proposed_by", Text, nullable=False),
    Column("decided_by", Text),
    Column("decided_at", DateTime(timezone=True)),
    Column("reason", Text),
    Column("policy_version", Integer),
    Column(
        "supersedes",
        UUID(as_uuid=True),
        ForeignKey("editorial_decision.id", ondelete="RESTRICT"),
    ),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint(_in(DECISION_STATUSES), name="status"),
    Index("ix_editorial_decision_status", "status"),
)
