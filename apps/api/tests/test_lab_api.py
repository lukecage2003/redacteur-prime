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

UNKNOWN = "00000000-0000-0000-0000-000000000000"


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


def test_theory_flow(ctx: SimpleNamespace, comic_factory: SimpleNamespace) -> None:
    client = ctx.client
    path = comic_factory.pdf(pages=2)
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
            "texts": [{"text": "Je suis Diana, princesse.", "speaker": "Diana", "panel_index": 1}],
        },
    )
    created = client.post(
        "/api/v1/lab/theories",
        json={
            "title": "Diana est princesse",
            "claim": "Diana est de sang royal.",
            "document_ids": [doc],
            "subjects": ["Diana"],
        },
    )
    assert created.status_code == 201
    theory_id = created.json()["theory_id"]

    evidence = {
        "theory_id": theory_id,
        "role": "SUPPORTS",
        "document_id": doc,
        "page": 1,
        "panel": 1,
        "excerpt": "princesse",
    }
    added = client.post("/api/v1/lab/evidence", json=evidence)
    assert added.status_code == 201
    assert added.json()["verified"] is True
    wrong = client.post("/api/v1/lab/evidence", json={**evidence, "excerpt": "reine"})
    assert wrong.status_code == 422
    assert "absent" in wrong.json()["detail"]
    assert client.post("/api/v1/lab/research", json={"theory_id": theory_id}).status_code == 200
    alt = client.post(
        "/api/v1/lab/alternatives", json={"theory_id": theory_id, "text": "Un titre honorifique."}
    )
    assert alt.status_code == 201

    theory = client.get(f"/api/v1/lab/theories/{theory_id}").json()
    assert (theory["level"], theory["status"]) == ("THEORY", "SUPPORTED")
    assert theory["alternatives"][0]["text"] == "Un titre honorifique."
    assert [d["id"] for d in theory["documents"]] == [doc]
    assert [t["id"] for t in client.get("/api/v1/lab/theories?level=THEORY").json()] == [theory_id]
    assert client.get("/api/v1/lab/theories?status=REFUTED").json() == []

    retracted = client.post(
        "/api/v1/lab/evidence/retractions",
        json={"evidence_id": added.json()["id"], "reason": "trop vague"},
    )
    assert retracted.json()["level"] == "SPECULATION"

    mission = client.post(
        "/api/v1/editorial/missions", json={"type": "THEORY_REVIEW", "theory_id": theory_id}
    )
    assert mission.status_code == 202
    ctx.drain()
    review = client.get(f"/api/v1/editorial/missions/{mission.json()['mission_id']}").json()
    assert review["status"] == "AWAITING_APPROVAL"
    assert review["result"]["deliverable"].startswith("# Revue de théorie : Diana est princesse")


def test_lab_validation(ctx: SimpleNamespace) -> None:
    client = ctx.client
    assert client.get(f"/api/v1/lab/theories/{UNKNOWN}").status_code == 404
    bad_doc = client.post(
        "/api/v1/lab/theories", json={"title": "t", "claim": "c", "document_ids": [UNKNOWN]}
    )
    assert bad_doc.status_code == 422
    assert client.post("/api/v1/lab/research", json={"theory_id": UNKNOWN}).status_code == 404
    assert (
        client.post(
            "/api/v1/lab/evidence/retractions", json={"evidence_id": UNKNOWN, "reason": "x"}
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/v1/editorial/missions", json={"type": "THEORY_REVIEW", "theory_id": UNKNOWN}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/editorial/missions", json={"type": "FACT_CHECK", "draft": "x"}
        ).status_code
        == 422
    )
