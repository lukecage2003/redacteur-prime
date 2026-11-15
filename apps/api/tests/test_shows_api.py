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


def _approve_all(client: TestClient) -> None:
    for d in client.get("/api/v1/governance/decisions?decision_status=PROPOSED").json():
        client.post(
            "/api/v1/governance/decide", json={"decision_id": d["id"], "decision": "approve"}
        )


def test_show_flow(client: TestClient) -> None:
    created = client.post(
        "/api/v1/creative/series",
        json={
            "name": "Enquêtes",
            "promise": "Un mystère des Endless",
            "identity": "enquête",
            "tone": "sobre",
            "structure": ["Mystère"],
            "target_minutes": 10,
            "art_direction": "charte",
            "evolution": "un par mois",
            "languages": ["fr", "en"],
        },
    )
    series_id = created.json()["series_id"]
    assert client.get(f"/api/v1/shows/{series_id}").json()["status"] == "DRAFT"
    _approve_all(client)
    assert client.get(f"/api/v1/shows/{series_id}").json()["status"] == "TESTING"
    bad = client.post("/api/v1/shows/transitions", json={"series_id": series_id, "to": "DRAFT"})
    assert bad.status_code == 422
    fmt = client.post(
        "/api/v1/shows/formats",
        json={
            "series_id": series_id,
            "name": "Short",
            "platform": "YOUTUBE_SHORTS",
            "language": "en",
            "min_minutes": 0.5,
            "max_minutes": 1,
            "structure": ["Hook"],
        },
    )
    assert fmt.status_code == 201
    guidelines = client.post(
        "/api/v1/shows/guidelines", json={"series_id": series_id, "changes": {"tone": "vif"}}
    )
    assert guidelines.json()["version"] == 2
    _approve_all(client)
    show = client.get(f"/api/v1/shows/{series_id}").json()
    assert show["tone"] == "vif"
    assert show["formats"][0]["language"] == "en"
    fit = client.get("/api/v1/shows/fit", params={"subject": "Les Endless expliqués"}).json()
    assert fit["shows"][0]["name"] == "Enquêtes"
    assert client.get(f"/api/v1/shows/{series_id}/performance").json()["contents"] == 0
    missing = client.get("/api/v1/shows/00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 404
