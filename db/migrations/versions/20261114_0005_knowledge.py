"""Knowledge Intelligence : entités, alias, relations prouvées, corrections, index de recherche.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
ENTITY_TYPES = (
    "'CHARACTER', 'EVENT', 'LOCATION', 'OBJECT', 'CONCEPT', 'SERIES', 'CONTINUITY', 'COMIC'"
)
RELATION_TYPES = "'APPEARS_IN', 'REFERENCES', 'CONTRADICTS', 'PRECEDES', 'REVEALS', 'FORESHADOWS', 'RELATED_TO', 'OPPOSES'"
LEVELS = "'CANON', 'INTERPRETATION', 'THEORY', 'SPECULATION'"


def _id() -> sa.Column:  # type: ignore[type-arg]
    return sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False)


def _created() -> sa.Column:  # type: ignore[type-arg]
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def _updated() -> sa.Column:  # type: ignore[type-arg]
    return sa.Column(
        "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "entity",
        _id(),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("canonical_name", sa.Text(), nullable=False),
        sa.Column("folded_name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("merged_into", UUID, nullable=True),
        _created(),
        _updated(),
        sa.CheckConstraint(f"type IN ({ENTITY_TYPES})", name=op.f("ck_entity_type")),
        sa.ForeignKeyConstraint(
            ["merged_into"],
            ["entity.id"],
            name=op.f("fk_entity_merged_into_entity"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_entity")),
    )
    op.create_index("ix_entity_type_folded_name", "entity", ["type", "folded_name"])

    op.create_table(
        "entity_alias",
        _id(),
        sa.Column("entity_id", UUID, nullable=False),
        sa.Column("alias", sa.Text(), nullable=False),
        sa.Column("folded", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=True),
        sa.Column("origin", sa.Text(), nullable=False),
        _created(),
        sa.CheckConstraint("origin IN ('EXTRACTOR', 'HUMAN')", name=op.f("ck_entity_alias_origin")),
        sa.ForeignKeyConstraint(
            ["entity_id"],
            ["entity.id"],
            name=op.f("fk_entity_alias_entity_id_entity"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_entity_alias")),
        sa.UniqueConstraint("entity_id", "folded", name=op.f("uq_entity_alias_entity_id_folded")),
    )
    op.create_index("ix_entity_alias_folded", "entity_alias", ["folded"])

    op.create_table(
        "relation",
        _id(),
        sa.Column("relation_key", sa.Text(), nullable=False),
        sa.Column("source_id", UUID, nullable=False),
        sa.Column("target_id", UUID, nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("qualifier", sa.Text(), nullable=True),
        sa.Column("level", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("origin", sa.Text(), nullable=False),
        sa.Column("retracted_at", sa.DateTime(timezone=True), nullable=True),
        _created(),
        _updated(),
        sa.CheckConstraint(f"type IN ({RELATION_TYPES})", name=op.f("ck_relation_type")),
        sa.CheckConstraint(f"level IN ({LEVELS})", name=op.f("ck_relation_level")),
        sa.CheckConstraint("origin IN ('EXTRACTOR', 'HUMAN')", name=op.f("ck_relation_origin")),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name=op.f("ck_relation_confidence")
        ),
        sa.CheckConstraint("source_id <> target_id", name=op.f("ck_relation_not_self")),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["entity.id"],
            name=op.f("fk_relation_source_id_entity"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["target_id"],
            ["entity.id"],
            name=op.f("fk_relation_target_id_entity"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_relation")),
        sa.UniqueConstraint("relation_key", name=op.f("uq_relation_relation_key")),
    )
    op.create_index("ix_relation_source_id", "relation", ["source_id"])
    op.create_index("ix_relation_target_id", "relation", ["target_id"])

    op.create_table(
        "relation_evidence",
        _id(),
        sa.Column("relation_id", UUID, nullable=False),
        sa.Column("observation_id", UUID, nullable=True),
        sa.Column("document_id", UUID, nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("panel_index", sa.Integer(), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=True),
        _created(),
        sa.CheckConstraint("page_number >= 1", name=op.f("ck_relation_evidence_page_number")),
        sa.ForeignKeyConstraint(
            ["relation_id"],
            ["relation.id"],
            name=op.f("fk_relation_evidence_relation_id_relation"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["observation_id"],
            ["observation.id"],
            name=op.f("fk_relation_evidence_observation_id_observation"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["document.id"],
            name=op.f("fk_relation_evidence_document_id_document"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_relation_evidence")),
        sa.UniqueConstraint(
            "relation_id",
            "observation_id",
            name=op.f("uq_relation_evidence_relation_id_observation_id"),
        ),
    )
    op.create_index("ix_relation_evidence_relation_id", "relation_evidence", ["relation_id"])

    op.create_table(
        "correction",
        _id(),
        sa.Column("target_type", sa.Text(), nullable=False),
        sa.Column("target_id", UUID, nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("before", postgresql.JSONB(), nullable=True),
        sa.Column("after", postgresql.JSONB(), nullable=True),
        sa.Column("author", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        _created(),
        sa.CheckConstraint(
            "target_type IN ('ENTITY', 'RELATION')", name=op.f("ck_correction_target_type")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_correction")),
    )
    op.create_index("ix_correction_target_id", "correction", ["target_id"])

    op.create_table(
        "search_document",
        _id(),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("ref_id", UUID, nullable=False),
        sa.Column("document_id", UUID, nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("panel_index", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("folded", sa.Text(), nullable=False),
        sa.Column("embedder", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(), nullable=False),
        _created(),
        sa.CheckConstraint("kind IN ('TEXT', 'ENTITY')", name=op.f("ck_search_document_kind")),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["document.id"],
            name=op.f("fk_search_document_document_id_document"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_search_document")),
        sa.UniqueConstraint(
            "kind", "ref_id", "embedder", name=op.f("uq_search_document_kind_ref_id_embedder")
        ),
    )
    op.create_index("ix_search_document_document_id", "search_document", ["document_id"])
    # Plein texte : index GIN sur l'expression (non déclaré dans le schéma SQLAlchemy).
    op.execute(
        "CREATE INDEX ix_search_document_fts ON search_document "
        "USING gin (to_tsvector('simple', folded))"
    )


def downgrade() -> None:
    # Réservé au développement et à la CI. Voir docs/operations/migrations.md.
    op.drop_index("ix_search_document_fts", table_name="search_document")
    op.drop_index("ix_search_document_document_id", table_name="search_document")
    op.drop_table("search_document")
    op.drop_index("ix_correction_target_id", table_name="correction")
    op.drop_table("correction")
    op.drop_index("ix_relation_evidence_relation_id", table_name="relation_evidence")
    op.drop_table("relation_evidence")
    op.drop_index("ix_relation_target_id", table_name="relation")
    op.drop_index("ix_relation_source_id", table_name="relation")
    op.drop_table("relation")
    op.drop_index("ix_entity_alias_folded", table_name="entity_alias")
    op.drop_table("entity_alias")
    op.drop_index("ix_entity_type_folded_name", table_name="entity")
    op.drop_table("entity")
