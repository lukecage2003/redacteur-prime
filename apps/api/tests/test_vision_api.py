import asyncio
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from primestone.config import Settings
from primestone.jobs import PostgresJobQueue
from primestone_api.main import create_app
from primestone_worker.main import Worker, build_registry

pytestmark = pytest.mark.integration


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        storage_local_root=tmp_path / "storage",
        render_max_dimension=600,
    )


@pytest.fixture
def client(settings: Settings, db_engine: Engine) -> Iterator[TestClient]:
    with TestClient(create_app(settings, engine=db_engine)) as c:
        yield c


def process_all(settings: Settings, engine: Engine) -> None:
    worker = Worker(PostgresJobQueue(engine), build_registry(settings, engine), worker_id="t")

    async def run() -> None:
        for _ in range(3):
            while await worker.run_once():
                pass

    asyncio.run(run())


def test_estimate_analyze_and_read(
    client: TestClient, settings: Settings, db_engine: Engine, comic_factory: SimpleNamespace
) -> None:
    path = comic_factory.pdf(pages=2)
    imported = client.post(
        "/api/v1/library/imports",
        files=[("files", (path.name, path.read_bytes(), "application/pdf"))],
    ).json()
    process_all(settings, db_engine)
    document_id = imported["items"][0]["document_id"]
    body = {"document_ids": [document_id], "provider": "fake", "budget_usd": "0.50"}

    estimate = client.post("/api/v1/vision/estimates", json=body).json()
    assert (estimate["to_analyze"], estimate["estimated_cost_usd"]) == (2, "0.0000")

    assert (
        client.get(f"/api/v1/library/documents/{document_id}/pages/1/analysis").status_code == 404
    )
    started = client.post("/api/v1/vision/analyses", json=body)
    assert started.status_code == 202
    process_all(settings, db_engine)

    report = client.get(f"/api/v1/vision/analyses/{started.json()['run_id']}").json()
    assert (report["status"], report["pages_succeeded"]) == ("SUCCEEDED", 2)
    analysis = client.get(f"/api/v1/library/documents/{document_id}/pages/1/analysis").json()
    assert len(analysis["panels"]) == 3
    assert analysis["provider"] == "fake"


def test_unknown_provider_and_validation(client: TestClient) -> None:
    body = {
        "document_ids": ["00000000-0000-0000-0000-000000000000"],
        "provider": "nope",
        "budget_usd": "1",
    }
    assert client.post("/api/v1/vision/analyses", json=body).status_code == 422
    assert (
        client.post(
            "/api/v1/vision/analyses", json={**body, "provider": "fake", "budget_usd": "-1"}
        ).status_code
        == 422
    )
    assert (
        client.post("/api/v1/vision/analyses", json={**body, "document_ids": []}).status_code == 422
    )
    assert (
        client.get("/api/v1/vision/analyses/00000000-0000-0000-0000-000000000000").status_code
        == 404
    )
