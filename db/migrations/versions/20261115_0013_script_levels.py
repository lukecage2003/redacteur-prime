"""Audience Bridge : niveau de connaissance d'un script et variantes par niveau.

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("script", sa.Column("level", sa.Text(), nullable=True))
    op.add_column("script", sa.Column("level_of", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_check_constraint(
        op.f("ck_script_level"),
        "script",
        "level IS NULL OR level IN ('DISCOVERY', 'EXPLORATION', 'EXPERTISE')",
    )
    op.create_foreign_key(
        op.f("fk_script_level_of_script"),
        "script",
        "script",
        ["level_of"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    # Réservé au développement et à la CI. Voir docs/operations/migrations.md.
    op.drop_constraint(op.f("fk_script_level_of_script"), "script", type_="foreignkey")
    op.drop_constraint(op.f("ck_script_level"), "script", type_="check")
    op.drop_column("script", "level_of")
    op.drop_column("script", "level")
