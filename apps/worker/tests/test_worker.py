from typing import Any

import pytest
from sqlalchemy import Engine

from primestone.jobs import PostgresJobQueue, StepStatus
from primestone_worker.handlers import HandlerRegistry, PermanentError, registry
from primestone_worker.main import Worker


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_ping_handler() -> None:
    result = await registry.get("system.ping")({"echo": "bonjour"})
    assert result == {"pong": True, "echo": "bonjour"}


def test_unknown_handler_is_permanent() -> None:
    with pytest.raises(PermanentError):
        HandlerRegistry().get("inconnu")


def test_duplicate_registration_rejected() -> None:
    reg = HandlerRegistry()

    @reg.register("a")
    async def a(payload: dict[str, Any]) -> dict[str, Any]:
        return {}

    with pytest.raises(ValueError, match="déjà"):
        reg.register("a")(a)


@pytest.mark.anyio
@pytest.mark.integration
async def test_worker_processes_steps_end_to_end(db_engine: Engine) -> None:
    queue = PostgresJobQueue(db_engine)
    handlers = HandlerRegistry()
    calls = {"flaky": 0}

    @handlers.register("ok")
    async def ok(payload: dict[str, Any]) -> dict[str, Any]:
        return {"double": payload["n"] * 2}

    @handlers.register("flaky")
    async def flaky(payload: dict[str, Any]) -> dict[str, Any]:
        calls["flaky"] += 1
        if calls["flaky"] == 1:
            raise ConnectionError("réseau")
        return {}

    run = queue.create_run("test")
    ok_id = queue.enqueue(run, "ok", {"n": 21}, idempotency_key="ok")
    flaky_id = queue.enqueue(run, "flaky", {}, idempotency_key="flaky")
    unknown_id = queue.enqueue(run, "inconnu", {}, idempotency_key="unknown")

    worker = Worker(queue, handlers, worker_id="test", retry_delay_seconds=0)
    while await worker.run_once():
        pass

    assert queue.step_status(ok_id) is StepStatus.SUCCEEDED
    assert queue.step_status(flaky_id) is StepStatus.SUCCEEDED
    assert calls["flaky"] == 2
    assert queue.step_status(unknown_id) is StepStatus.DEAD  # pas de nouvelle tentative
    assert queue.run_status(run) == "FAILED"
