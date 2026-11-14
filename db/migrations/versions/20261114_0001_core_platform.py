"""Socle : extensions PostgreSQL et file de tâches durable (pipeline_run, pipeline_step).

Revision ID: 0001
Revises:
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # pgvector (recherche sémantique, Phase 5) ; gen_random_uuid() est natif depuis PG 13.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "pipeline_run",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'PENDING'"), nullable=False),
        sa.Column(
            "params", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED')",
            name=op.f("ck_pipeline_run_status"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pipeline_run")),
    )

    op.create_table(
        "pipeline_step",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'PENDING'"), nullable=False),
        sa.Column(
            "payload", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default=sa.text("3"), nullable=False),
        sa.Column(
            "available_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED', 'DEAD')",
            name=op.f("ck_pipeline_step_status"),
        ),
        sa.CheckConstraint(
            "attempts >= 0 AND max_attempts >= 1", name=op.f("ck_pipeline_step_attempts")
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["pipeline_run.id"],
            name=op.f("fk_pipeline_step_run_id_pipeline_run"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pipeline_step")),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_pipeline_step_idempotency_key")),
    )
    op.create_index("ix_pipeline_step_claim", "pipeline_step", ["status", "available_at"])
    op.create_index("ix_pipeline_step_run_id", "pipeline_step", ["run_id"])


def downgrade() -> None:
    # Réservé au développement et à la CI (aller-retour). Ne jamais exécuter en production
    # sans sauvegarde validée : voir docs/operations/migrations.md.
    op.drop_index("ix_pipeline_step_run_id", table_name="pipeline_step")
    op.drop_index("ix_pipeline_step_claim", table_name="pipeline_step")
    op.drop_table("pipeline_step")
    op.drop_table("pipeline_run")
    # L'extension `vector` est conservée volontairement (partagée, non destructive).
