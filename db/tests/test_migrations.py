"""Les migrations s'appliquent, sont réversibles, et le schéma déclaré correspond à la base."""

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from conftest import alembic_config
from sqlalchemy import Engine, inspect, text

from primestone.db import metadata

pytestmark = pytest.mark.integration


def test_round_trip(database_url: str, migrated_engine: Engine) -> None:
    cfg = alembic_config(database_url)
    command.downgrade(cfg, "base")
    assert "pipeline_step" not in inspect(migrated_engine).get_table_names()
    command.upgrade(cfg, "head")
    tables = set(inspect(migrated_engine).get_table_names())
    assert {"pipeline_run", "pipeline_step", "comic", "document", "page", "import_item"} <= tables


def test_models_match_migrations(migrated_engine: Engine) -> None:
    with migrated_engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), metadata)
    assert diff == [], f"schéma et migrations divergent : {diff}"


def test_pgvector_available(migrated_engine: Engine) -> None:
    with migrated_engine.connect() as conn:
        version = conn.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        ).scalar_one_or_none()
    assert version is not None
