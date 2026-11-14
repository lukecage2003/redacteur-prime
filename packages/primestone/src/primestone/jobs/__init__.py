"""File de tâches durable adossée à PostgreSQL (ADR-0004).

Garanties : idempotence à l'enfilage, réservation concurrente sans doublon
(`FOR UPDATE SKIP LOCKED`), nouvelles tentatives bornées avec délai,
reprise après panne via expiration des baux (`recover_stale`).
"""

from primestone.jobs.errors import PermanentError
from primestone.jobs.queue import ClaimedStep, PostgresJobQueue, StepStatus

__all__ = ["ClaimedStep", "PermanentError", "PostgresJobQueue", "StepStatus"]
