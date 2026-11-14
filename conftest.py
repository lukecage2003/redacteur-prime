"""Fixtures partagées.

Les tests marqués `integration` utilisent une base PostgreSQL + pgvector JETABLE désignée par
PRIMESTONE_TEST_DATABASE_URL (service CI ou `docker compose`). Garde-fou : le nom de la base
doit contenir « test ». Les tables sont migrées avec Alembic puis vidées entre les tests.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).parent


def alembic_config(url: str) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


@pytest.fixture(scope="session")
def database_url() -> str:
    url = os.environ.get("PRIMESTONE_TEST_DATABASE_URL")
    if not url:
        pytest.skip("PRIMESTONE_TEST_DATABASE_URL non défini (tests d'intégration ignorés)")
    if "test" not in (make_url(url).database or ""):
        pytest.fail("garde-fou : le nom de la base de test doit contenir « test »")
    return url


@pytest.fixture(scope="session")
def migrated_engine(database_url: str) -> Iterator[Engine]:
    command.upgrade(alembic_config(database_url), "head")
    engine = create_engine(database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def db_engine(migrated_engine: Engine) -> Engine:
    """Moteur migré ; les tables de la file sont vidées avant chaque test (base de test)."""
    with migrated_engine.begin() as conn:
        conn.execute(text("DELETE FROM pipeline_step"))
        conn.execute(text("DELETE FROM pipeline_run"))
    return migrated_engine
