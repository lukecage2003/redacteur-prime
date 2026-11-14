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
def ctx(tmp_path: Path, db_engine: Engine) -> Iterator[SimpleNamespace]:
    settings = Settings(_env_file=None, environment="test", storage_local_root=tmp_path / "s")
    worker = Worker(PostgresJobQueue(db_engine), build_registry(settings, db_engine), worker_id="t")

    def drain() -> None:
        async def run() -> None:
            for _ in range(3):
                while await worker.run_once():
                    pass

        asyncio.run(run())

    with TestClient(create_app(settings, engine=db_engine)) as client:
        yield SimpleNamespace(client=client, drain=drain)


def test_mission_flow(ctx: SimpleNamespace, comic_factory: SimpleNamespace) -> None:
    client = ctx.client
    path = comic_factory.pdf(pages=1)
    doc = client.post(
        "/api/v1/library/imports",
        files=[("files", (path.name, path.read_bytes(), "application/pdf"))],
    ).json()["items"][0]["document_id"]
    ctx.drain()
    client.post(
        "/api/v1/transcriptions",
        json={
            "document_id": doc,
            "page": 1,
            "texts": [
                {"text": "Je suis Diana. J'ai 25 ans.", "speaker": "Diana", "panel_index": 1}
            ],
        },
    )

    agents = client.get("/api/v1/editorial/agents").json()
    assert {a["key"] for a in agents if a["available"]} >= {"fact_checker", "research_director"}

    created = client.post(
        "/api/v1/editorial/missions",
        json={"type": "CHARACTER_DOSSIER", "document_ids": [doc], "character": "Diana"},
    )
    assert created.status_code == 202
    ctx.drain()
    mission = client.get(f"/api/v1/editorial/missions/{created.json()['mission_id']}").json()
    assert mission["status"] == "AWAITING_APPROVAL"
    assert mission["result"]["fact_check"]["verdict"] in ("PASS", "NEEDS_REVIEW")
    approval = mission["approvals"][0]["id"]
    decided = client.post(
        "/api/v1/editorial/approvals", json={"approval_id": approval, "decision": "approve"}
    )
    assert decided.status_code == 201
    assert client.get("/api/v1/editorial/missions").json()[0]["status"] == "APPROVED"

    bad = client.post(
        "/api/v1/editorial/missions",
        json={
            "type": "FACT_CHECK",
            "document_ids": [doc],
            "draft": "Diana a 30 ans dans ce récit.",
        },
    )
    ctx.drain()
    failed = client.get(f"/api/v1/editorial/missions/{bad.json()['mission_id']}").json()
    assert failed["result"]["recommendation"] == "NE PAS VALIDER"
    refused = client.post(
        "/api/v1/editorial/approvals",
        json={"approval_id": failed["approvals"][0]["id"], "decision": "approve"},
    )
    assert refused.status_code == 422
    assert "erreur factuelle" in refused.json()["detail"]


def test_validation(ctx: SimpleNamespace) -> None:
    client = ctx.client
    unknown_doc = "00000000-0000-0000-0000-000000000000"
    assert (
        client.post(
            "/api/v1/editorial/missions",
            json={"type": "CHARACTER_DOSSIER", "document_ids": [unknown_doc]},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/editorial/missions",
            json={"type": "CONTINUITY_AUDIT", "document_ids": [unknown_doc]},
        ).status_code
        == 422
    )
    assert client.get(f"/api/v1/editorial/missions/{unknown_doc}").status_code == 404
    assert (
        client.post(
            "/api/v1/editorial/approvals", json={"approval_id": unknown_doc, "decision": "approve"}
        ).status_code
        == 404
    )
