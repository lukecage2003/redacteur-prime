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
def client(tmp_path: Path, db_engine: Engine) -> Iterator[TestClient]:
    settings = Settings(_env_file=None, environment="test", storage_local_root=tmp_path / "s")
    with TestClient(create_app(settings, engine=db_engine)) as c:
        c.settings = settings  # type: ignore[attr-defined]
        yield c


def test_knowledge_flow(
    client: TestClient, db_engine: Engine, comic_factory: SimpleNamespace
) -> None:
    path = comic_factory.pdf(pages=1)
    doc = client.post(
        "/api/v1/library/imports",
        files=[("files", (path.name, path.read_bytes(), "application/pdf"))],
    ).json()["items"][0]["document_id"]
    worker = Worker(
        PostgresJobQueue(db_engine), build_registry(client.settings, db_engine), worker_id="t"
    )  # type: ignore[attr-defined]

    async def run() -> None:
        for _ in range(3):
            while await worker.run_once():
                pass

    asyncio.run(run())
    client.post(
        "/api/v1/transcriptions",
        json={
            "document_id": doc,
            "page": 1,
            "texts": [
                {"text": "Je suis Diana.", "speaker": "Diana", "panel_index": 1},
                {"text": "Diana, attends !", "speaker": "Steve", "panel_index": 1},
            ],
        },
    )
    client.post("/api/v1/forensic/analyses", json={"document_ids": [doc]})
    built = client.post("/api/v1/knowledge/build", json={"document_ids": [doc]})
    assert built.status_code == 201
    assert built.json()["relations"] >= 2

    characters = client.get("/api/v1/knowledge/entities", params={"type": "CHARACTER"}).json()
    ids = {e["canonical_name"]: e["id"] for e in characters}
    assert {"Diana", "Steve"} <= set(ids)
    diana = client.get(f"/api/v1/knowledge/entities/{ids['Diana']}").json()
    assert any(r["type"] == "APPEARS_IN" and r["level"] == "CANON" for r in diana["relations"])

    graph = client.get(f"/api/v1/knowledge/entities/{ids['Diana']}/graph").json()
    assert ids["Steve"] in {n["id"] for n in graph["nodes"]}
    route = client.get(
        "/api/v1/knowledge/path", params={"from_id": ids["Diana"], "to_id": ids["Steve"]}
    ).json()
    assert route["found"] is True

    alias = client.post(
        "/api/v1/knowledge/corrections",
        json={
            "action": "add_alias",
            "entity_id": ids["Diana"],
            "value": "Wonder Woman",
            "reason": "identité connue",
        },
    )
    assert alias.status_code == 201
    no_reason = client.post(
        "/api/v1/knowledge/corrections",
        json={"action": "rename", "entity_id": ids["Diana"], "value": "X", "reason": ""},
    )
    assert no_reason.status_code == 422
    manual = client.post(
        "/api/v1/knowledge/relations",
        json={
            "source_id": ids["Steve"],
            "target_id": ids["Diana"],
            "type": "RELATED_TO",
            "qualifier": "allié",
            "level": "INTERPRETATION",
            "reason": "lecture",
            "evidence": [{"document_id": doc, "page": 1, "panel": 1}],
        },
    )
    assert manual.status_code == 201
    theory = client.post(
        "/api/v1/knowledge/relations",
        json={
            "source_id": ids["Steve"],
            "target_id": ids["Diana"],
            "type": "RELATED_TO",
            "level": "THEORY",
            "reason": "x",
            "evidence": [{"document_id": doc, "page": 1}],
        },
    )
    assert theory.status_code == 422

    results = client.get("/api/v1/search", params={"q": "attends"}).json()
    assert results[0]["content"] == "Diana, attends !"
    assert results[0]["page"] == 1
    assert client.get("/api/v1/search").status_code == 422
    assert (
        client.get("/api/v1/knowledge/entities/00000000-0000-0000-0000-000000000000").status_code
        == 404
    )
