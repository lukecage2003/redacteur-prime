"""Tests d'intégration de la file durable : idempotence, concurrence, reprise après panne."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import Engine, text

from primestone.jobs import PostgresJobQueue, StepStatus

pytestmark = pytest.mark.integration


@pytest.fixture
def queue(db_engine: Engine) -> PostgresJobQueue:
    return PostgresJobQueue(db_engine)


def test_enqueue_is_idempotent(queue: PostgresJobQueue) -> None:
    run = queue.create_run("comic.import", {"batch": "b1"})
    a = queue.enqueue(run, "comic.render_page", {"page": 1}, idempotency_key="doc1:p1:render")
    b = queue.enqueue(run, "comic.render_page", {"page": 1}, idempotency_key="doc1:p1:render")
    assert a == b
    assert queue.run_status(run) == "RUNNING"


def test_claim_complete_marks_run_succeeded(queue: PostgresJobQueue) -> None:
    run = queue.create_run("test")
    queue.enqueue(run, "system.ping", {}, idempotency_key="k1")
    step = queue.claim("w1")
    assert step is not None
    assert step.attempts == 1
    assert queue.claim("w2") is None  # rien d'autre de disponible
    queue.complete(step, {"ok": True})
    assert queue.step_status(step.id) is StepStatus.SUCCEEDED
    assert queue.run_status(run) == "SUCCEEDED"


def test_retry_then_dead(queue: PostgresJobQueue) -> None:
    run = queue.create_run("test")
    queue.enqueue(run, "flaky", {}, idempotency_key="k", max_attempts=2)

    first = queue.claim("w")
    assert first is not None
    assert queue.fail(first, "boom", retry_delay_seconds=0) is StepStatus.PENDING

    second = queue.claim("w")
    assert second is not None
    assert second.attempts == 2
    assert queue.fail(second, "boom", retry_delay_seconds=0) is StepStatus.DEAD
    assert queue.run_status(run) == "FAILED"


def test_retry_delay_is_respected(queue: PostgresJobQueue) -> None:
    run = queue.create_run("test")
    queue.enqueue(run, "flaky", {}, idempotency_key="k")
    step = queue.claim("w")
    assert step is not None
    queue.fail(step, "boom", retry_delay_seconds=3600)
    assert queue.claim("w") is None


def test_recover_stale_after_crash(queue: PostgresJobQueue, db_engine: Engine) -> None:
    run = queue.create_run("test")
    queue.enqueue(run, "long", {}, idempotency_key="k")
    step = queue.claim("crashed-worker")
    assert step is not None
    # Simule un worker tué il y a une heure sans avoir terminé.
    with db_engine.begin() as conn:
        conn.execute(
            text("UPDATE pipeline_step SET locked_at = now() - interval '1 hour' WHERE id = :id"),
            {"id": step.id},
        )
    assert queue.recover_stale(lease_seconds=60) == 1
    resumed = queue.claim("new-worker")
    assert resumed is not None
    assert resumed.id == step.id
    assert resumed.attempts == 2


def test_fresh_lease_is_not_recovered(queue: PostgresJobQueue) -> None:
    run = queue.create_run("test")
    queue.enqueue(run, "long", {}, idempotency_key="k")
    assert queue.claim("w") is not None
    assert queue.recover_stale(lease_seconds=3600) == 0


def test_concurrent_claims_never_duplicate(queue: PostgresJobQueue) -> None:
    run = queue.create_run("comic.import")
    for page in range(1, 61):  # un lot de 60 étapes
        queue.enqueue(run, "comic.render_page", {"page": page}, idempotency_key=f"p{page}")

    def drain(worker: str) -> list[int]:
        pages = []
        while (step := queue.claim(worker)) is not None:
            pages.append(step.payload["page"])
            queue.complete(step, {})
        return pages

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(drain, [f"w{i}" for i in range(6)]))

    claimed = [p for r in results for p in r]
    assert sorted(claimed) == list(range(1, 61))  # chaque étape traitée exactement une fois
    assert queue.run_status(run) == "SUCCEEDED"
