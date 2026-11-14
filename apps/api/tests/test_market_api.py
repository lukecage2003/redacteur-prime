from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from primestone.config import Settings
from primestone_api.main import create_app

pytestmark = pytest.mark.integration

FICHE = {"access": "saisie manuelle", "quota": "aucun", "terms_url": "https://ex.test/terms"}


@pytest.fixture
def ctx(tmp_path: Path, db_engine: Engine) -> Iterator[SimpleNamespace]:
    settings = Settings(_env_file=None, environment="test", storage_local_root=tmp_path / "s")
    with TestClient(create_app(settings, engine=db_engine)) as client:
        yield SimpleNamespace(client=client)


def test_market_flow(ctx: SimpleNamespace) -> None:
    client = ctx.client
    assert (
        client.post(
            "/api/v1/market/sources",
            json={"key": "manuel", "name": "Relevés", "kind": "MANUAL", **FICHE},
        ).status_code
        == 201
    )
    now = datetime.now(UTC).isoformat()
    record = {
        "platform": "youtube",
        "external_id": "x1",
        "title": "Sandman explained",
        "language": "en",
        "observed_at": now,
        "views": 1000,
    }
    body = {"source": "manuel", "records": [record]}
    refused = client.post("/api/v1/market/imports", json=body)
    assert refused.status_code == 422
    assert "non validée" in refused.json()["detail"]
    assert (
        client.post("/api/v1/market/sources/verifications", json={"key": "manuel"}).status_code
        == 201
    )
    private = client.post(
        "/api/v1/market/imports", json={"source": "manuel", "records": [{**record, "ctr": 4.1}]}
    )
    assert private.status_code == 422
    imported = client.post("/api/v1/market/imports", json=body)
    assert imported.status_code == 201
    assert imported.json()["metrics"] == 1
    assert (
        client.post(
            "/api/v1/market/topics", json={"name": "Sandman", "keywords_en": ["sandman"]}
        ).status_code
        == 201
    )
    analysis = client.get("/api/v1/market/analysis?min_items=1").json()
    assert analysis["topics"][0]["status"] == "SCORED"
    assert analysis["data_class"] == "ESTIMATE"
    assert client.get("/api/v1/market/sources").json()[0]["items"] == 1
    assert client.get("/api/v1/market/collections").json()[0]["status"] == "SUCCEEDED"
    no_key = client.post(
        "/api/v1/market/sources",
        json={"key": "yt", "name": "YouTube", "kind": "YOUTUBE_API", **FICHE},
    )
    assert no_key.status_code == 201
    client.post("/api/v1/market/sources/verifications", json={"key": "yt"})
    blocked = client.post("/api/v1/market/collections", json={"source": "yt", "query": "sandman"})
    assert blocked.status_code == 422
    assert "non configurée" in blocked.json()["detail"]
    assert client.post("/api/v1/market/collections", json={"source": "nope"}).status_code == 404

    mission = client.post("/api/v1/editorial/missions", json={"type": "MARKET_BRIEF"})
    assert mission.status_code == 202
