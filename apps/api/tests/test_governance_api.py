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


def test_governance_flow(client: TestClient) -> None:
    assert client.get("/api/v1/governance/brands").json()[0]["slug"] == "primestone"
    created = client.post(
        "/api/v1/governance/pillars", json={"name": "Enquêtes", "description": "Preuves"}
    )
    assert created.status_code == 201
    pending = client.get("/api/v1/governance/decisions?decision_status=PROPOSED").json()
    assert len(pending) == 1
    body = {"decision_id": pending[0]["id"], "decision": "approve"}
    assert client.post("/api/v1/governance/decide", json=body).json()["status"] == "APPROVED"
    assert client.post("/api/v1/governance/decide", json=body).status_code == 422
    assert client.get("/api/v1/governance/pillars").json()[0]["status"] == "ACTIVE"
    revert = {"decision_id": pending[0]["id"], "decision": "revert", "reason": "essai"}
    assert client.post("/api/v1/governance/decide", json=revert).json()["status"] == "REVERTED"
    bad = client.post(
        "/api/v1/governance/policies",
        json={"action": "POLICY_CHANGE", "requires_approval": False},
    )
    assert bad.status_code == 422
    charter = client.post(
        "/api/v1/creative/charter",
        json={"name": "v1", "rules": {"colors": [], "fonts": [], "tone": {}, "thumbnail": {}}},
    )
    assert charter.status_code == 201
    assert client.get("/api/v1/creative/charter").json()["version"] == 0  # brouillon
