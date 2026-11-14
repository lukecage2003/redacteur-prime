"""Editorial Director : missions, tâches d'agents, demandes d'approbation, traces d'appels.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()


def _id() -> sa.Column:  # type: ignore[type-arg]
    return sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False)


def _now(name: str) -> sa.Column:  # type: ignore[type-arg]
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def upgrade() -> None:
    op.create_table(
        "mission",
        _id(),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'PLANNED'"), nullable=False),
        sa.Column("document_ids", JSONB, nullable=False),
        sa.Column("params", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("result", JSONB, nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("run_id", UUID, nullable=True),
        _now("created_at"),
        _now("updated_at"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('PLANNED', 'RUNNING', 'AWAITING_APPROVAL', 'APPROVED', 'REJECTED', 'FAILED')",
            name=op.f("ck_mission_status"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["pipeline_run.id"],
            name=op.f("fk_mission_run_id_pipeline_run"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mission")),
    )
    op.create_table(
        "mission_task",
        _id(),
        sa.Column("mission_id", UUID, nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("agent", sa.Text(), nullable=False),
        sa.Column("critical", sa.Boolean(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'PENDING'"), nullable=False),
        sa.Column("input", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("output", JSONB, nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED', 'SKIPPED')",
            name=op.f("ck_mission_task_status"),
        ),
        sa.ForeignKeyConstraint(
            ["mission_id"],
            ["mission.id"],
            name=op.f("fk_mission_task_mission_id_mission"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mission_task")),
        sa.UniqueConstraint(
            "mission_id", "position", name=op.f("uq_mission_task_mission_id_position")
        ),
    )
    op.create_table(
        "approval_request",
        _id(),
        sa.Column("mission_id", UUID, nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'PENDING'"), nullable=False),
        sa.Column("decided_by", sa.Text(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        _now("created_at"),
        sa.CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'REJECTED')", name=op.f("ck_approval_request_status")
        ),
        sa.ForeignKeyConstraint(
            ["mission_id"],
            ["mission.id"],
            name=op.f("fk_approval_request_mission_id_mission"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_approval_request")),
    )
    op.create_index("ix_approval_request_mission_id", "approval_request", ["mission_id"])
    op.create_table(
        "agent_run",
        _id(),
        sa.Column("mission_task_id", UUID, nullable=False),
        sa.Column("agent", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("prompt_id", sa.Text(), nullable=True),
        sa.Column("prompt_version", sa.Text(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("cost_usd", sa.Numeric(12, 6), server_default=sa.text("0"), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        _now("created_at"),
        sa.ForeignKeyConstraint(
            ["mission_task_id"],
            ["mission_task.id"],
            name=op.f("fk_agent_run_mission_task_id_mission_task"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_run")),
    )
    op.create_index("ix_agent_run_mission_task_id", "agent_run", ["mission_task_id"])


def downgrade() -> None:
    # Réservé au développement et à la CI. Voir docs/operations/migrations.md.
    op.drop_index("ix_agent_run_mission_task_id", table_name="agent_run")
    op.drop_table("agent_run")
    op.drop_index("ix_approval_request_mission_id", table_name="approval_request")
    op.drop_table("approval_request")
    op.drop_table("mission_task")
    op.drop_table("mission")
