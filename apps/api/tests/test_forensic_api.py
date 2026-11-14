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
    return Settings(_env_file=None, environment="test", storage_local_root=tmp_path / "s")


@pytest.fixture
def client(settings: Settings, db_engine: Engine) -> Iterator[TestClient]:
    with TestClient(create_app(settings, engine=db_engine)) as c:
        yield c


def imported(client: TestClient, settings: Settings, engine: Engine, path: Path) -> str:
    body = client.post(
        "/api/v1/library/imports",
        files=[("files", (path.name, path.read_bytes(), "application/pdf"))],
    ).json()
    worker = Worker(PostgresJobQueue(engine), build_registry(settings, engine), worker_id="t")

    async def run() -> None:
        for _ in range(3):
            while await worker.run_once():
                pass

    asyncio.run(run())
    return str(body["items"][0]["document_id"])


def test_transcribe_analyze_report(
    client: TestClient, settings: Settings, db_engine: Engine, comic_factory: SimpleNamespace
) -> None:
    doc = imported(client, settings, db_engine, comic_factory.pdf(pages=1))
    panels = client.get(f"/api/v1/library/documents/{doc}/pages/1/panels").json()
    assert [p["index"] for p in panels] == [1, 2, 3]  # détectées sans analyse préalable
    assert client.get(f"/api/v1/library/documents/{doc}/pages/9/panels").status_code == 404
    put = client.put(
        f"/api/v1/library/documents/{doc}/pages/1/transcription",
        json={"texts": [{"text": "J'ai 30 ans.", "speaker": "Diana", "panel_index": 2}]},
    )
    assert put.status_code == 201
    analysis = client.get(f"/api/v1/library/documents/{doc}/pages/1/analysis").json()
    assert analysis["provider"] == "human"
    assert analysis["texts"][0]["panel_index"] == 2

    assert client.post("/api/v1/forensic/analyses", json={"document_ids": [doc]}).status_code == 201
    report = client.get("/api/v1/forensic/report", params={"document_ids": [doc]}).json()
    assert report["status"] == "COMPLETE"
    assert report["characters"]["Diana"]["speeches"] == 1
    claims = client.get(
        "/api/v1/forensic/observations", params={"document_ids": [doc], "kind": "CLAIM"}
    ).json()
    assert claims[0]["value"] == "30"
    assert claims[0]["evidence"][0]["page"] == 1


def test_errors(
    client: TestClient, settings: Settings, db_engine: Engine, comic_factory: SimpleNamespace
) -> None:
    doc = imported(client, settings, db_engine, comic_factory.pdf(pages=1))
    bad_panel = client.put(
        f"/api/v1/library/documents/{doc}/pages/1/transcription",
        json={"texts": [{"text": "x", "panel_index": 42}]},
    )
    assert bad_panel.status_code == 422
    missing = client.put(
        f"/api/v1/library/documents/{doc}/pages/9/transcription", json={"texts": []}
    )
    assert missing.status_code == 404
    assert client.get("/api/v1/forensic/report").status_code == 422


def test_paid_provider_refused_by_default(client: TestClient) -> None:
    body = {
        "document_ids": ["00000000-0000-0000-0000-000000000000"],
        "provider": "claude",
        "budget_usd": "5",
    }
    response = client.post("/api/v1/vision/analyses", json=body)
    assert response.status_code == 422
    assert "zéro coût" in response.json()["detail"]
