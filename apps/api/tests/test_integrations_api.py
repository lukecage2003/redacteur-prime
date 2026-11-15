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

SCRIPT = """00:00 - Introduction
Et si Diana n'était pas celle que vous croyez ? Tout tient en une phrase.
Pourtant, personne ne la remarque.

01:00 - L'aveu
Diana le dit elle-même : « Je suis Diana, princesse. » [{title}, p. 1, case 1].
Mais pourquoi l'avouer si tôt ? Vous allez voir que la réponse est dans la case suivante.

02:00 - Conclusion
En résumé, l'aveu change tout. Et vous, l'aviez-vous remarqué ?"""


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


def test_integrations(ctx: SimpleNamespace, comic_factory: SimpleNamespace) -> None:
    client = ctx.client
    path = comic_factory.pdf(pages=1)
    item = client.post(
        "/api/v1/library/imports",
        files=[("files", (path.name, path.read_bytes(), "application/pdf"))],
    ).json()["items"][0]
    doc = item["document_id"]
    ctx.drain()
    page = client.get(f"/api/v1/integrations/panel-explorer/documents/{doc}/pages/1").json()
    assert (page["contract"], page["transcribed"], page["texts"]) == ("1.1", False, [])
    assert page["panels"]
    client.post(
        "/api/v1/transcriptions",
        json={
            "document_id": doc,
            "page": 1,
            "texts": [{"text": "Je suis Diana, princesse.", "speaker": "Diana", "panel_index": 1}],
        },
    )
    page = client.get(f"/api/v1/integrations/panel-explorer/documents/{doc}/pages/1").json()
    assert page["transcribed"] is True
    assert page["texts"][0]["text"] == "Je suis Diana, princesse."
    assert (
        client.get(f"/api/v1/integrations/panel-explorer/documents/{doc}/pages/9").status_code
        == 404
    )

    title = client.get("/api/v1/library/documents").json()[0]["title"]
    script_id = client.post(
        "/api/v1/scripts",
        json={
            "title": "Aveu",
            "language": "fr",
            "content": SCRIPT.format(title=title),
            "document_ids": [doc],
        },
    ).json()["script_id"]
    assert client.get(f"/api/v1/integrations/motion-studio/scripts/{script_id}").status_code == 409
    score = client.post("/api/v1/scripts/evaluations", json={"script_id": script_id}).json()
    assert score["factual_veto"] is False, score["analysis"]["fact_check"]
    assert (
        client.post("/api/v1/scripts/validations", json={"script_id": script_id}).status_code == 201
    )
    export = client.get(f"/api/v1/integrations/motion-studio/scripts/{script_id}").json()
    assert [s["start_seconds"] for s in export["sections"]] == [0, 60, 120]
    assert export["score"] >= 70
    assert export["intents"][1]["visual_moments"][0].startswith("Montrer la case citée")
