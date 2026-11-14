from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine

from primestone.config import Settings
from primestone_api.main import create_app


def client_for(engine: Engine) -> Iterator[TestClient]:
    app = create_app(Settings(_env_file=None, environment="test"), engine=engine)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def broken_client() -> Iterator[TestClient]:
    # Port 1 : aucune base n'écoute, la connexion échoue immédiatement.
    engine = create_engine(
        "postgresql+psycopg://x:x@127.0.0.1:1/none", connect_args={"connect_timeout": 1}
    )
    yield from client_for(engine)


def test_liveness_does_not_need_database(broken_client: TestClient) -> None:
    response = broken_client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["environment"] == "test"


def test_readiness_reports_database_failure(broken_client: TestClient) -> None:
    response = broken_client.get("/api/v1/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["checks"]["database"].startswith("error")


def test_openapi_is_versioned(broken_client: TestClient) -> None:
    response = broken_client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    assert "/api/v1/health" in response.json()["paths"]


@pytest.mark.integration
def test_readiness_with_database(db_engine: Engine) -> None:
    for client in client_for(db_engine):
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 200
        assert response.json()["checks"] == {"database": "ok"}
