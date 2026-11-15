"""Audience Intelligence & communauté : segments, preuves, liens du graphe d'audience,
commentaires publics anonymisés.

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()


def _id() -> sa.Column:  # type: ignore[type-arg]
    return sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False)


def _now(name: str) -> sa.Column:  # type: ignore[type-arg]
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def _fk(table: str, column: str, target: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], [f"{target}.id"], name=op.f(f"fk_{table}_{column}_{target}"), ondelete="RESTRICT"
    )


def upgrade() -> None:
    op.create_table(
        "audience_segment",
        _id(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("motivations", JSONB, nullable=False),
        sa.Column("knowledge_level", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'HYPOTHESIS'"), nullable=False),
        sa.Column("author", sa.Text(), nullable=False),
        _now("created_at"),
        _now("updated_at"),
        sa.CheckConstraint(
            "status IN ('HYPOTHESIS', 'CONFIRMED')", name=op.f("ck_audience_segment_status")
        ),
        sa.CheckConstraint(
            "knowledge_level IS NULL OR knowledge_level IN ('NOVICE', 'INTERMEDIATE', 'EXPERT')",
            name=op.f("ck_audience_segment_knowledge_level"),
        ),
        sa.CheckConstraint(
            "jsonb_array_length(motivations) >= 1", name=op.f("ck_audience_segment_motivations")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audience_segment")),
        sa.UniqueConstraint("name", name=op.f("uq_audience_segment_name")),
    )
    op.create_table(
        "audience_evidence",
        _id(),
        sa.Column("segment_id", UUID, nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("data", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("data_class", sa.Text(), nullable=False),
        sa.Column("added_by", sa.Text(), nullable=False),
        _now("created_at"),
        sa.Column("retracted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "kind IN ('METRIC', 'COMMENT_CLUSTER', 'MARKET', 'DECLARED')",
            name=op.f("ck_audience_evidence_kind"),
        ),
        sa.CheckConstraint(
            "data_class IN ('PUBLIC', 'PRIVATE_AUTHORIZED', 'ESTIMATE', 'HYPOTHESIS')",
            name=op.f("ck_audience_evidence_data_class"),
        ),
        _fk("audience_evidence", "segment_id", "audience_segment"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audience_evidence")),
    )
    op.create_index("ix_audience_evidence_segment_id", "audience_evidence", ["segment_id"])
    op.create_table(
        "audience_link",
        _id(),
        sa.Column("segment_id", UUID, nullable=False),
        sa.Column("target_kind", sa.Text(), nullable=False),
        sa.Column("target", sa.Text(), nullable=False),
        sa.Column("relation", sa.Text(), nullable=False),
        sa.Column("evidence_id", UUID, nullable=False),
        _now("created_at"),
        sa.CheckConstraint(
            "target_kind IN ('ENTITY', 'TOPIC', 'FORMAT', 'PLATFORM')",
            name=op.f("ck_audience_link_target_kind"),
        ),
        sa.CheckConstraint(
            "relation IN ('INTERESTED_IN', 'PREFERS', 'USES', 'ASKS_ABOUT', 'FRUSTRATED_BY')",
            name=op.f("ck_audience_link_relation"),
        ),
        _fk("audience_link", "segment_id", "audience_segment"),
        _fk("audience_link", "evidence_id", "audience_evidence"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audience_link")),
        sa.UniqueConstraint(
            "segment_id",
            "target_kind",
            "target",
            "relation",
            name=op.f("uq_audience_link_segment_id_target_kind_target_relation"),
        ),
    )
    op.create_table(
        "community_comment",
        _id(),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("content_id", UUID, nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("like_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        _now("fetched_at"),
        sa.CheckConstraint(
            "kind IN ('QUESTION', 'THEORY', 'REQUEST', 'CONTROVERSY', 'PRAISE', 'OTHER')",
            name=op.f("ck_community_comment_kind"),
        ),
        _fk("community_comment", "content_id", "content_item"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_community_comment")),
        sa.UniqueConstraint(
            "platform", "external_id", name=op.f("uq_community_comment_platform_external_id")
        ),
    )


def downgrade() -> None:
    # Réservé au développement et à la CI. Voir docs/operations/migrations.md.
    op.drop_table("community_comment")
    op.drop_table("audience_link")
    op.drop_index("ix_audience_evidence_segment_id", table_name="audience_evidence")
    op.drop_table("audience_evidence")
    op.drop_table("audience_segment")
