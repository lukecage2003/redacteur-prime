"""Identité indépendante : profils de voix (licence obligatoire) et profils visuels.

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def _common(table: str) -> list[sa.schema.SchemaItem]:
    return [
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("brand_id", UUID, nullable=False),
        sa.ForeignKeyConstraint(
            ["brand_id"],
            ["media_brand.id"],
            name=op.f(f"fk_{table}_brand_id_media_brand"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{table}")),
    ]


def upgrade() -> None:
    op.create_table(
        "brand_voice_profile",
        *_common("brand_voice_profile"),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("tone", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("voice", sa.Text(), nullable=False),
        sa.Column("license", sa.Text(), nullable=False),
        sa.Column("license_url", sa.Text(), nullable=True),
        sa.Column("allowed_use", sa.Text(), nullable=False),
        sa.Column("consent_reference", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'PROPOSED'"), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "language IN ('fr', 'en')", name=op.f("ck_brand_voice_profile_language")
        ),
        sa.CheckConstraint(
            "kind IN ('SYNTHETIC', 'HUMAN_LICENSED')", name=op.f("ck_brand_voice_profile_kind")
        ),
        sa.CheckConstraint(
            "status IN ('PROPOSED', 'APPROVED', 'RETIRED')",
            name=op.f("ck_brand_voice_profile_status"),
        ),
        sa.CheckConstraint(
            "length(trim(license)) > 0", name=op.f("ck_brand_voice_profile_license")
        ),
        sa.CheckConstraint(
            "kind = 'SYNTHETIC' OR length(trim(coalesce(consent_reference, ''))) > 0",
            name=op.f("ck_brand_voice_profile_consent"),
        ),
        sa.UniqueConstraint("brand_id", "name", name=op.f("uq_brand_voice_profile_brand_id_name")),
    )
    op.create_table(
        "brand_visual_profile",
        *_common("brand_visual_profile"),
        sa.Column("series_id", UUID, nullable=True),
        sa.Column("platform", sa.Text(), nullable=True),
        sa.Column("language", sa.Text(), nullable=True),
        sa.Column("rules", postgresql.JSONB(), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'ACTIVE'"), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "language IS NULL OR language IN ('fr', 'en')",
            name=op.f("ck_brand_visual_profile_language"),
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'RETIRED')", name=op.f("ck_brand_visual_profile_status")
        ),
        sa.ForeignKeyConstraint(
            ["series_id"],
            ["series.id"],
            name=op.f("fk_brand_visual_profile_series_id_series"),
            ondelete="RESTRICT",
        ),
    )


def downgrade() -> None:
    # Réservé au développement et à la CI. Voir docs/operations/migrations.md.
    op.drop_table("brand_visual_profile")
    op.drop_table("brand_voice_profile")
