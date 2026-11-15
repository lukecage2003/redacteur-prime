"""Moteur d'émissions : cycle de vie, formats, versions des règles, épisodes étendus,
rattachement des scripts, contenus, missions et expériences à une émission.

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()
SHOW_LINKED = ("script", "content_item", "mission", "experiment")


def _fk(table: str, column: str, target: str) -> None:
    op.create_foreign_key(
        op.f(f"fk_{table}_{column}_{target}"), table, target, [column], ["id"], ondelete="RESTRICT"
    )


def _drop_fk(table: str, column: str, target: str) -> None:
    op.drop_constraint(op.f(f"fk_{table}_{column}_{target}"), table, type_="foreignkey")


def upgrade() -> None:
    # Cycle de vie complet ; l'existant est conservé (PAUSED → SUSPENDED, ENDED → RETIRED).
    op.drop_constraint(op.f("ck_series_status"), "series", type_="check")
    op.execute(
        "UPDATE series SET status = CASE status WHEN 'PAUSED' THEN 'SUSPENDED' "
        "WHEN 'ENDED' THEN 'RETIRED' ELSE status END"
    )
    op.create_check_constraint(
        op.f("ck_series_status"),
        "series",
        "status IN ('DRAFT', 'TESTING', 'ACTIVE', 'SUSPENDED', 'RETIRED')",
    )
    op.alter_column("series", "status", server_default=sa.text("'DRAFT'"))
    op.add_column("series", sa.Column("expertise_level", sa.Text(), nullable=True))
    op.add_column(
        "series",
        sa.Column("languages", JSONB, server_default=sa.text("'[\"fr\"]'::jsonb"), nullable=False),
    )
    op.add_column(
        "series",
        sa.Column(
            "evidence_requirements", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
    )
    op.add_column("series", sa.Column("pillar_id", UUID, nullable=True))
    _fk("series", "pillar_id", "editorial_pillar")
    op.add_column(
        "series",
        sa.Column("guideline_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_series_expertise_level"),
        "series",
        "expertise_level IS NULL OR expertise_level IN ('DISCOVERY', 'EXPLORATION', 'EXPERTISE')",
    )
    op.create_table(
        "show_format",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("series_id", UUID, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("min_minutes", sa.Numeric(6, 2), nullable=False),
        sa.Column("max_minutes", sa.Numeric(6, 2), nullable=False),
        sa.Column("structure", JSONB, nullable=False),
        sa.Column("rules", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'ACTIVE'"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("language IN ('fr', 'en')", name=op.f("ck_show_format_language")),
        sa.CheckConstraint(
            "min_minutes > 0 AND max_minutes >= min_minutes", name=op.f("ck_show_format_minutes")
        ),
        sa.CheckConstraint("status IN ('ACTIVE', 'RETIRED')", name=op.f("ck_show_format_status")),
        sa.ForeignKeyConstraint(
            ["series_id"],
            ["series.id"],
            name=op.f("fk_show_format_series_id_series"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_show_format")),
        sa.UniqueConstraint(
            "series_id", "name", "language", name=op.f("uq_show_format_series_id_name_language")
        ),
    )
    op.create_table(
        "show_guideline_version",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("series_id", UUID, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("guidelines", JSONB, nullable=False),
        sa.Column("decision_id", UUID, nullable=False),
        sa.Column("author", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["series_id"],
            ["series.id"],
            name=op.f("fk_show_guideline_version_series_id_series"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["decision_id"],
            ["editorial_decision.id"],
            name=op.f("fk_show_guideline_version_decision_id_editorial_decision"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_show_guideline_version")),
        sa.UniqueConstraint(
            "series_id", "version", name=op.f("uq_show_guideline_version_series_id_version")
        ),
    )
    # Épisodes : format, langue, statut, contenu publié déclaré, version des règles.
    op.add_column("series_episode", sa.Column("format_id", UUID, nullable=True))
    _fk("series_episode", "format_id", "show_format")
    op.add_column("series_episode", sa.Column("language", sa.Text(), nullable=True))
    op.add_column(
        "series_episode",
        sa.Column("status", sa.Text(), server_default=sa.text("'PROPOSED'"), nullable=False),
    )
    op.add_column("series_episode", sa.Column("content_id", UUID, nullable=True))
    _fk("series_episode", "content_id", "content_item")
    op.add_column("series_episode", sa.Column("guideline_version", sa.Integer(), nullable=True))
    op.create_check_constraint(
        op.f("ck_series_episode_language"),
        "series_episode",
        "language IS NULL OR language IN ('fr', 'en')",
    )
    op.create_check_constraint(
        op.f("ck_series_episode_status"),
        "series_episode",
        "status IN ('PROPOSED', 'IN_PRODUCTION', 'APPROVED', 'PUBLISHED')",
    )
    for table in SHOW_LINKED:
        op.add_column(table, sa.Column("show_id", UUID, nullable=True))
        _fk(table, "show_id", "series")
    op.add_column("script", sa.Column("format_id", UUID, nullable=True))
    _fk("script", "format_id", "show_format")
    op.add_column("experiment", sa.Column("language", sa.Text(), nullable=True))
    op.create_check_constraint(
        op.f("ck_experiment_language"), "experiment", "language IS NULL OR language IN ('fr', 'en')"
    )
    op.execute(
        "INSERT INTO editorial_policy (brand_id, action, requires_approval, note) "
        "SELECT id, 'SHOW_GUIDELINES', true, 'politique initiale (phase 21)' FROM media_brand "
        "WHERE slug = 'primestone' ON CONFLICT DO NOTHING"
    )


def downgrade() -> None:
    # Réservé au développement et à la CI. Voir docs/operations/migrations.md.
    op.execute("DELETE FROM editorial_policy WHERE action = 'SHOW_GUIDELINES'")
    op.drop_constraint(op.f("ck_experiment_language"), "experiment", type_="check")
    op.drop_column("experiment", "language")
    _drop_fk("script", "format_id", "show_format")
    op.drop_column("script", "format_id")
    for table in reversed(SHOW_LINKED):
        _drop_fk(table, "show_id", "series")
        op.drop_column(table, "show_id")
    op.drop_constraint(op.f("ck_series_episode_status"), "series_episode", type_="check")
    op.drop_constraint(op.f("ck_series_episode_language"), "series_episode", type_="check")
    _drop_fk("series_episode", "content_id", "content_item")
    _drop_fk("series_episode", "format_id", "show_format")
    for column in ("guideline_version", "content_id", "status", "language", "format_id"):
        op.drop_column("series_episode", column)
    op.drop_table("show_guideline_version")
    op.drop_table("show_format")
    op.drop_constraint(op.f("ck_series_expertise_level"), "series", type_="check")
    _drop_fk("series", "pillar_id", "editorial_pillar")
    for column in ("guideline_version", "pillar_id", "evidence_requirements", "languages"):
        op.drop_column("series", column)
    op.drop_column("series", "expertise_level")
    op.drop_constraint(op.f("ck_series_status"), "series", type_="check")
    op.execute(
        "UPDATE series SET status = CASE status WHEN 'SUSPENDED' THEN 'PAUSED' "
        "WHEN 'RETIRED' THEN 'ENDED' WHEN 'ACTIVE' THEN 'ACTIVE' ELSE 'PAUSED' END"
    )
    op.create_check_constraint(
        op.f("ck_series_status"), "series", "status IN ('ACTIVE', 'PAUSED', 'ENDED')"
    )
    op.alter_column("series", "status", server_default=sa.text("'ACTIVE'"))
