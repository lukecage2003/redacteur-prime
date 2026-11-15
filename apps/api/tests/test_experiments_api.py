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


def test_objectives_and_experiments(client: TestClient) -> None:
    csv = "Content,Video title,Views,Impressions click-through rate (%)\nv1,Une,100,8\n"
    assert client.post("/api/v1/performance/imports", json={"csv": csv}).status_code == 201
    content_id = client.get("/api/v1/performance/contents").json()[0]["id"]
    ok = client.post(
        "/api/v1/performance/objectives",
        json={"content_id": content_id, "objective": "DISCOVERY", "format": "LONG"},
    )
    assert ok.status_code == 201
    bad = client.post(
        "/api/v1/performance/objectives", json={"content_id": content_id, "objective": "VIRAL"}
    )
    assert bad.status_code == 422
    report = client.get("/api/v1/performance/objectives-report").json()
    assert report["evaluations"][0]["objective"] == "DISCOVERY"
    assert client.get(f"/api/v1/performance/contents/{content_id}/retention").json() == []

    exp = client.post(
        "/api/v1/performance/experiments",
        json={"title": "T", "hypothesis": "H", "variable": "TITLE", "metric": "ctr"},
    ).json()["experiment_id"]
    for label, n, s in (("A", 5000, 400), ("B", 5000, 250)):
        assert (
            client.post(
                "/api/v1/performance/experiments/variants",
                json={
                    "experiment_id": exp,
                    "label": label,
                    "description": label,
                    "exposures": n,
                    "successes": s,
                },
            ).status_code
            == 201
        )
    result = client.post(
        "/api/v1/performance/experiments/conclusions", json={"experiment_id": exp}
    ).json()
    assert (result["status"], result["winner"]) == ("CONCLUDED", "A")
    assert client.get("/api/v1/performance/experiments").json()[0]["status"] == "CONCLUDED"
    missing = client.post(
        "/api/v1/performance/experiments/variants",
        json={
            "experiment_id": "00000000-0000-0000-0000-000000000000",
            "label": "A",
            "description": "x",
            "reported_share": 0.5,
        },
    )
    assert missing.status_code == 404
