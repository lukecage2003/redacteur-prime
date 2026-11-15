"""Marque et gouvernance : media_brand (PRIMESTONE par défaut), piliers, politiques,
journal des décisions, règles de marque approuvées, rattachement des données à la marque.

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()
LINKED = ("series", "script", "content_item", "mission", "experiment", "brand_charter")
# Actions sensibles : approbation du fondateur exigée (modifiable ensuite par décision).
POLICIES = {
    "CHARTER_CHANGE": True,
    "PILLAR_CHANGE": True,
    "SHOW_LIFECYCLE": True,
    "SCRIPT_FINAL_VALIDATION": True,
    "DISTRIBUTION_PLAN": True,
    "VOICE_PROFILE": True,
    "COST_SETTINGS": True,
    "POLICY_CHANGE": True,
    "PACKAGING_PROPOSAL": False,
    "SCRIPT_DRAFT": False,
}


def _id() -> sa.Column:  # type: ignore[type-arg]
    return sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False)


def _now(name: str) -> sa.Column:  # type: ignore[type-arg]
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def _brand_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["brand_id"],
        ["media_brand.id"],
        name=op.f(f"fk_{table}_brand_id_media_brand"),
        ondelete="RESTRICT",
    )


def upgrade() -> None:
    op.create_table(
        "media_brand",
        _id(),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("mission", sa.Text(), nullable=False),
        sa.Column("languages", JSONB, nullable=False),
        sa.Column("primary_language", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'ACTIVE'"), nullable=False),
        _now("created_at"),
        sa.CheckConstraint("status IN ('ACTIVE', 'ARCHIVED')", name=op.f("ck_media_brand_status")),
        sa.CheckConstraint(
            "primary_language IN ('fr', 'en')", name=op.f("ck_media_brand_primary_language")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_media_brand")),
        sa.UniqueConstraint("slug", name=op.f("uq_media_brand_slug")),
    )
    op.execute(
        "INSERT INTO media_brand (slug, name, mission, languages, primary_language) VALUES "
        "('primestone', 'PRIMESTONE', 'Média comics international : enquêtes et explications "
        "sourcées, en français puis en anglais.', '[\"fr\", \"en\"]', 'fr')"
    )
    op.create_table(
        "editorial_pillar",
        _id(),
        sa.Column("brand_id", UUID, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("rules", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'PROPOSED'"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        _now("created_at"),
        sa.CheckConstraint(
            "status IN ('PROPOSED', 'ACTIVE', 'RETIRED')", name=op.f("ck_editorial_pillar_status")
        ),
        _brand_fk("editorial_pillar"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_editorial_pillar")),
        sa.UniqueConstraint("brand_id", "name", name=op.f("uq_editorial_pillar_brand_id_name")),
    )
    op.create_table(
        "editorial_policy",
        _id(),
        sa.Column("brand_id", UUID, nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("requires_approval", sa.Boolean(), nullable=False),
        sa.Column("approver", sa.Text(), server_default=sa.text("'FOUNDER'"), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        _now("updated_at"),
        _brand_fk("editorial_policy"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_editorial_policy")),
        sa.UniqueConstraint("brand_id", "action", name=op.f("uq_editorial_policy_brand_id_action")),
    )
    for action, required in POLICIES.items():
        op.execute(
            sa.text(
                "INSERT INTO editorial_policy (brand_id, action, requires_approval, note) "
                "SELECT id, :a, :r, 'politique initiale (phase 20)' FROM media_brand "
                "WHERE slug = 'primestone'"
            ).bindparams(a=action, r=required)
        )
    op.create_table(
        "editorial_decision",
        _id(),
        sa.Column("brand_id", UUID, nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("subject_type", sa.Text(), nullable=False),
        sa.Column("subject_id", sa.Text(), nullable=True),
        sa.Column("proposal", JSONB, nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'PROPOSED'"), nullable=False),
        sa.Column("proposed_by", sa.Text(), nullable=False),
        sa.Column("decided_by", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("policy_version", sa.Integer(), nullable=True),
        sa.Column("supersedes", UUID, nullable=True),
        _now("created_at"),
        sa.CheckConstraint(
            "status IN ('PROPOSED', 'APPROVED', 'REJECTED', 'SUPERSEDED', 'REVERTED')",
            name=op.f("ck_editorial_decision_status"),
        ),
        _brand_fk("editorial_decision"),
        sa.ForeignKeyConstraint(
            ["supersedes"],
            ["editorial_decision.id"],
            name=op.f("fk_editorial_decision_supersedes_editorial_decision"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_editorial_decision")),
    )
    op.create_index("ix_editorial_decision_status", "editorial_decision", ["status"])
    # Règles de marque : statut d'approbation et langue ; l'existant reste APPROUVÉ.
    op.add_column("brand_charter", sa.Column("language", sa.Text(), nullable=True))
    op.add_column(
        "brand_charter",
        sa.Column("status", sa.Text(), server_default=sa.text("'APPROVED'"), nullable=False),
    )
    op.add_column("brand_charter", sa.Column("approved_by", sa.Text(), nullable=True))
    op.add_column(
        "brand_charter", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_check_constraint(
        op.f("ck_brand_charter_status"),
        "brand_charter",
        "status IN ('DRAFT', 'APPROVED', 'RETIRED')",
    )
    op.create_check_constraint(
        op.f("ck_brand_charter_language"),
        "brand_charter",
        "language IS NULL OR language IN ('fr', 'en')",
    )
    op.execute("UPDATE brand_charter SET approved_by = author, approved_at = created_at")
    for table in LINKED:
        op.add_column(table, sa.Column("brand_id", UUID, nullable=True))
        op.create_foreign_key(
            op.f(f"fk_{table}_brand_id_media_brand"),
            table,
            "media_brand",
            ["brand_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        op.execute(
            f"UPDATE {table} SET brand_id = (SELECT id FROM media_brand WHERE slug = 'primestone')"  # noqa: S608 - nom de table constant
        )


def downgrade() -> None:
    # Réservé au développement et à la CI. Voir docs/operations/migrations.md.
    for table in reversed(LINKED):
        op.drop_constraint(op.f(f"fk_{table}_brand_id_media_brand"), table, type_="foreignkey")
        op.drop_column(table, "brand_id")
    op.drop_constraint(op.f("ck_brand_charter_language"), "brand_charter", type_="check")
    op.drop_constraint(op.f("ck_brand_charter_status"), "brand_charter", type_="check")
    for column in ("approved_at", "approved_by", "status", "language"):
        op.drop_column("brand_charter", column)
    op.drop_index("ix_editorial_decision_status", table_name="editorial_decision")
    op.drop_table("editorial_decision")
    op.drop_table("editorial_policy")
    op.drop_table("editorial_pillar")
    op.drop_table("media_brand")
