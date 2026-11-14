"""Schéma relationnel (source de vérité pour `alembic check`).

Toute évolution passe par une migration versionnée dans `db/migrations/versions/`.
Le schéma complet visé est décrit dans DATA_MODEL.md ; seules les tables
réellement implémentées figurent ici.
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Table,
    Text,
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
