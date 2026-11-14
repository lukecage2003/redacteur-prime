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
        render_max_dimension=128,
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


def upload(client: TestClient, *paths: Path) -> dict:  # type: ignore[type-arg]
    files = [("files", (p.name, p.read_bytes(), "application/octet-stream")) for p in paths]
    response = client.post("/api/v1/library/imports?label=test", files=files)
    assert response.status_code == 202, response.text
    return response.json()  # type: ignore[no-any-return]


def test_upload_process_and_browse(
    client: TestClient, settings: Settings, db_engine: Engine, comic_factory: SimpleNamespace
) -> None:
    body = upload(client, comic_factory.pdf(pages=2, name="un.pdf"), comic_factory.cbz(pages=3))
    assert [i["outcome"] for i in body["items"]] == ["NEW", "NEW"]
    run_id = body["run_id"]

    pending = client.get(f"/api/v1/library/imports/{run_id}").json()
    assert pending["status"] == "RUNNING"

    process_all(settings, db_engine)

    report = client.get(f"/api/v1/library/imports/{run_id}").json()
    assert report["status"] == "SUCCEEDED"
    assert report["totals"]["pages_rendered"] == 5

    documents = client.get("/api/v1/library/documents?status=COMPLETE").json()
    assert {d["original_filename"] for d in documents} >= {"un.pdf"}
    doc = next(d for d in documents if d["original_filename"] == "un.pdf")
    assert (doc["title"], doc["pages_rendered"]) == ("un", 2)

    detail = client.get(f"/api/v1/library/documents/{doc['id']}").json()
    assert [p["number"] for p in detail["pages"]] == [1, 2]
    assert all(p["status"] == "RENDERED" for p in detail["pages"])

    image = client.get(f"/api/v1/library/documents/{doc['id']}/pages/1/image")
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/webp"
    assert image.content[:4] == b"RIFF"


def test_client_paths_are_never_trusted(client: TestClient, comic_factory: SimpleNamespace) -> None:
    path = comic_factory.pdf(pages=1)
    response = client.post(
        "/api/v1/library/imports",
        files=[("files", ("../../etc/passwd.pdf", path.read_bytes(), "application/pdf"))],
    )
    assert response.status_code == 202
    assert response.json()["items"][0]["filename"] == "passwd.pdf"


def test_rejected_upload_is_reported(client: TestClient) -> None:
    response = client.post(
        "/api/v1/library/imports",
        files=[("files", ("notes.txt", b"bonjour", "text/plain"))],
    )
    item = response.json()["items"][0]
    assert (item["outcome"], item["document_id"]) == ("REJECTED", None)
    assert "format" in item["error"]


def test_not_found(client: TestClient) -> None:
    missing = "00000000-0000-0000-0000-000000000000"
    assert client.get(f"/api/v1/library/imports/{missing}").status_code == 404
    assert client.get(f"/api/v1/library/documents/{missing}").status_code == 404
    assert client.get(f"/api/v1/library/documents/{missing}/pages/1/image").status_code == 404


def test_upload_without_files(client: TestClient) -> None:
    assert client.post("/api/v1/library/imports").status_code == 422
