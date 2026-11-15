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


def test_distribution_flow(client: TestClient) -> None:
    channel = client.post(
        "/api/v1/distribution/channels",
        json={"platform": "YOUTUBE", "language": "fr", "handle": "@p", "name": "FR"},
    ).json()["channel_id"]
    item = client.post(
        "/api/v1/distribution/plan",
        json={"channel_id": channel, "title": "Teaser", "scheduled_for": "2026-12-01T18:00:00Z"},
    ).json()
    declare = {"item_id": item["item_id"], "url": "https://youtu.be/t", "external_id": "t"}
    assert client.post("/api/v1/distribution/plan/declarations", json=declare).status_code == 422
    client.post(
        "/api/v1/governance/decide",
        json={"decision_id": item["decision_id"], "decision": "approve"},
    )
    ok = client.post("/api/v1/distribution/plan/declarations", json=declare)
    assert ok.json()["status"] == "PUBLISHED"
    bad_url = declare | {"url": "http://x"}
    assert client.post("/api/v1/distribution/plan/declarations", json=bad_url).status_code == 422
    portfolio = client.post(
        "/api/v1/distribution/portfolios",
        json={
            "name": "Déc",
            "period_start": "2026-12-01",
            "period_end": "2026-12-31",
            "targets": {"language": {"fr": 0.5, "en": 0.5}},
        },
    ).json()["portfolio_id"]
    report = client.get(f"/api/v1/distribution/portfolios/{portfolio}").json()["balance"]
    assert report["items"] == 1
    assert report["alerts"]
    assert client.get("/api/v1/distribution/channels/performance").json()[0]["name"] == "FR"
