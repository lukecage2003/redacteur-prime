from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import Engine, bindparam, text
from sqlalchemy.dialects.postgresql import JSONB


class StepStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    DEAD = "DEAD"  # tentatives épuisées : intervention humaine requise


@dataclass(frozen=True)
class ClaimedStep:
    id: UUID
    run_id: UUID
    name: str
    payload: dict[str, Any]
    attempts: int
    max_attempts: int


_CLAIM = text(
    """
    UPDATE pipeline_step
       SET status = 'RUNNING', attempts = attempts + 1,
           locked_at = now(), locked_by = :worker_id, updated_at = now()
     WHERE id = (
           SELECT id FROM pipeline_step
            WHERE status = 'PENDING' AND available_at <= now()
            ORDER BY available_at, created_at
            FOR UPDATE SKIP LOCKED
            LIMIT 1)
    RETURNING id, run_id, name, payload, attempts, max_attempts
    """
)

_REFRESH_RUN = text(
    """
    UPDATE pipeline_run r
       SET status = CASE
             WHEN EXISTS (SELECT 1 FROM pipeline_step s
                           WHERE s.run_id = r.id AND s.status = 'DEAD') THEN 'FAILED'
             WHEN NOT EXISTS (SELECT 1 FROM pipeline_step s
                               WHERE s.run_id = r.id AND s.status IN ('PENDING', 'RUNNING'))
                  THEN 'SUCCEEDED'
             ELSE 'RUNNING' END,
           finished_at = CASE
             WHEN EXISTS (SELECT 1 FROM pipeline_step s
                           WHERE s.run_id = r.id AND s.status IN ('PENDING', 'RUNNING'))
                  THEN NULL
             ELSE now() END,
           updated_at = now()
     WHERE r.id = :run_id AND r.status <> 'CANCELLED'
    """
)


# Verrou de la ligne du lot : sérialise les fins d'étapes concurrentes d'un même lot, sinon
# deux workers terminant les deux dernières étapes se voient mutuellement « RUNNING » et le
# lot reste bloqué (bug reproduit par test_concurrent_claims_never_duplicate).
_LOCK_RUN = text("SELECT id FROM pipeline_run WHERE id = :run_id FOR UPDATE")


class PostgresJobQueue:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def create_run(self, kind: str, params: dict[str, Any] | None = None) -> UUID:
        stmt = text(
            "INSERT INTO pipeline_run (kind, params) VALUES (:kind, :params) RETURNING id"
        ).bindparams(bindparam("params", type_=JSONB))
        with self._engine.begin() as conn:
            run_id: UUID = conn.execute(stmt, {"kind": kind, "params": params or {}}).scalar_one()
        return run_id

    def enqueue(
        self,
        run_id: UUID,
        name: str,
        payload: dict[str, Any],
        *,
        idempotency_key: str,
        max_attempts: int = 3,
    ) -> UUID:
        """Enfile une étape. Idempotent : la même clé renvoie l'étape existante."""
        insert = text(
            """
            INSERT INTO pipeline_step (run_id, name, payload, idempotency_key, max_attempts)
            VALUES (:run_id, :name, :payload, :key, :max_attempts)
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING id
            """
        ).bindparams(bindparam("payload", type_=JSONB))
        with self._engine.begin() as conn:
            step_id = conn.execute(
                insert,
                {
                    "run_id": run_id,
                    "name": name,
                    "payload": payload,
                    "key": idempotency_key,
                    "max_attempts": max_attempts,
                },
            ).scalar_one_or_none()
            if step_id is None:
                step_id = conn.execute(
                    text("SELECT id FROM pipeline_step WHERE idempotency_key = :key"),
                    {"key": idempotency_key},
                ).scalar_one()
            conn.execute(
                text(
                    "UPDATE pipeline_run SET status = 'RUNNING', finished_at = NULL, "
                    "updated_at = now() WHERE id = :run_id AND status IN ('PENDING', 'SUCCEEDED')"
                ),
                {"run_id": run_id},
            )
        result: UUID = step_id
        return result

    def claim(self, worker_id: str) -> ClaimedStep | None:
        with self._engine.begin() as conn:
            row = conn.execute(_CLAIM, {"worker_id": worker_id}).mappings().one_or_none()
        if row is None:
            return None
        return ClaimedStep(
            id=row["id"],
            run_id=row["run_id"],
            name=row["name"],
            payload=dict(row["payload"]),
            attempts=row["attempts"],
            max_attempts=row["max_attempts"],
        )

    def complete(self, step: ClaimedStep, result: dict[str, Any]) -> None:
        stmt = text(
            """
            UPDATE pipeline_step
               SET status = 'SUCCEEDED', result = :result, error = NULL,
                   locked_at = NULL, locked_by = NULL, updated_at = now()
             WHERE id = :id AND status = 'RUNNING'
            """
        ).bindparams(bindparam("result", type_=JSONB))
        with self._engine.begin() as conn:
            conn.execute(_LOCK_RUN, {"run_id": step.run_id})
            conn.execute(stmt, {"id": step.id, "result": result})
            conn.execute(_REFRESH_RUN, {"run_id": step.run_id})

    def fail(
        self, step: ClaimedStep, error: str, *, retry_delay_seconds: float = 30.0
    ) -> StepStatus:
        """Échec : nouvelle tentative différée, ou DEAD si les tentatives sont épuisées."""
        final = step.attempts >= step.max_attempts
        status = StepStatus.DEAD if final else StepStatus.PENDING
        with self._engine.begin() as conn:
            conn.execute(_LOCK_RUN, {"run_id": step.run_id})
            conn.execute(
                text(
                    """
                    UPDATE pipeline_step
                       SET status = :status, error = :error,
                           available_at = now() + make_interval(secs => :delay),
                           locked_at = NULL, locked_by = NULL, updated_at = now()
                     WHERE id = :id AND status = 'RUNNING'
                    """
                ),
                {
                    "id": step.id,
                    "status": status.value,
                    "error": error[:10_000],
                    "delay": retry_delay_seconds,
                },
            )
            conn.execute(_REFRESH_RUN, {"run_id": step.run_id})
        return status

    def recover_stale(self, lease_seconds: int) -> int:
        """Reprise après panne : libère les étapes RUNNING dont le bail a expiré."""
        with self._engine.begin() as conn:
            rows = (
                conn.execute(
                    text(
                        """
                    UPDATE pipeline_step
                       SET status = CASE WHEN attempts >= max_attempts THEN 'DEAD'
                                         ELSE 'PENDING' END,
                           error = 'bail expiré (worker interrompu)',
                           locked_at = NULL, locked_by = NULL, updated_at = now()
                     WHERE status = 'RUNNING'
                       AND locked_at < now() - make_interval(secs => :lease)
                    RETURNING run_id
                    """
                    ),
                    {"lease": lease_seconds},
                )
                .scalars()
                .all()
            )
            for run_id in sorted(set(rows)):
                conn.execute(_LOCK_RUN, {"run_id": run_id})
                conn.execute(_REFRESH_RUN, {"run_id": run_id})
        return len(rows)

    def refresh_run(self, run_id: UUID) -> str:
        """Recalcule le statut d'un lot (ex. lot sans nouvelle étape : SUCCEEDED immédiat)."""
        with self._engine.begin() as conn:
            conn.execute(_LOCK_RUN, {"run_id": run_id})
            conn.execute(_REFRESH_RUN, {"run_id": run_id})
            status: str = conn.execute(
                text("SELECT status FROM pipeline_run WHERE id = :id"), {"id": run_id}
            ).scalar_one()
        return status

    def step_status(self, step_id: UUID) -> StepStatus:
        with self._engine.connect() as conn:
            value = conn.execute(
                text("SELECT status FROM pipeline_step WHERE id = :id"), {"id": step_id}
            ).scalar_one()
        return StepStatus(value)

    def run_status(self, run_id: UUID) -> str:
        with self._engine.connect() as conn:
            value: str = conn.execute(
                text("SELECT status FROM pipeline_run WHERE id = :id"), {"id": run_id}
            ).scalar_one()
        return value
