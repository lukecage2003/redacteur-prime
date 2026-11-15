from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from primestone.config import Settings
from primestone_api.main import create_app

pytestmark = pytest.mark.integration


@pytest.fixture
def client(tmp_path: Path, db_engine: Engine) -> Iterator[TestClient]:
    settings = Settings(_env_file=None, environment="test", storage_local_root=tmp_path / "s")
    with TestClient(create_app(settings, engine=db_engine)) as c:
        yield c


def test_memory_routes(client: TestClient) -> None:
    rights = {
        "kind": "MUSIC",
        "subject": "générique",
        "source": "bibliothèque libre",
        "basis": "LICENSE",
        "proof": "fiche de licence",
        "limits": "usage non commercial",
    }
    assert client.post("/api/v1/memory/rights", json=rights).status_code == 422  # licence ?
    ok = client.post("/api/v1/memory/rights", json=rights | {"license": "CC BY 4.0"})
    assert ok.status_code == 201
    assert client.get("/api/v1/memory/rights").json()[0]["kind"] == "MUSIC"
    lesson = {
        "lesson": "x",
        "source_type": "experiment",
        "source_id": "00000000-0000-0000-0000-000000000000",
    }
    assert client.post("/api/v1/memory/lessons", json=lesson).status_code == 404
    assert client.get("/api/v1/memory/costs").json()["total_usd"] == 0
    assert client.get("/api/v1/memory/journal").json() == []
