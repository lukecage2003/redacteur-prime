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


def test_identity_flow(client: TestClient) -> None:
    voice = {
        "name": "Voix EN",
        "language": "en",
        "tone": "calm",
        "provider": "piper",
        "voice": "local model",
        "license": "model licence",
        "allowed_use": "non-commercial narration",
    }
    assert client.post("/api/v1/identity/voices", json=voice | {"license": ""}).status_code == 422
    assert client.post("/api/v1/identity/voices", json=voice).status_code == 201
    assert client.get("/api/v1/identity/voices?language=en").json()[0]["status"] == "PROPOSED"
    assert client.get("/api/v1/identity/voices?language=fr").json() == []
    visual = {"rules": {"title_case": "phrase"}, "language": "fr"}
    assert client.post("/api/v1/identity/visuals", json=visual).status_code == 201
    en = client.get("/api/v1/identity/visuals/resolve?language=en").json()
    assert en["rules"] == {}
    missing = client.post(
        "/api/v1/identity/narrations", json={"script_id": "00000000-0000-0000-0000-000000000000"}
    )
    assert missing.status_code == 404
