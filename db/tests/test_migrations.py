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
    expected = {"pipeline_run", "pipeline_step", "comic", "document", "page", "import_item"}
    expected |= {"page_analysis", "panel", "text_region", "observation", "evidence_ref"}
    expected |= {"entity", "entity_alias", "relation", "relation_evidence", "correction"}
    expected |= {"search_document", "mission", "mission_task", "approval_request", "agent_run"}
    expected |= {"theory", "theory_evidence", "theory_alternative", "theory_event"}
    assert expected <= tables


def test_models_match_migrations(migrated_engine: Engine) -> None:
    with migrated_engine.connect() as conn:
        # Même exclusion que db/migrations/env.py : index plein texte créé en SQL brut.
        context = MigrationContext.configure(
            conn,
            opts={
                "include_object": lambda obj, name, type_, reflected, compare_to: (
                    not (type_ == "index" and name == "ix_search_document_fts")
                )
            },
        )
        diff = compare_metadata(context, metadata)
    assert diff == [], f"schéma et migrations divergent : {diff}"


def test_pgvector_available(migrated_engine: Engine) -> None:
    with migrated_engine.connect() as conn:
        version = conn.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        ).scalar_one_or_none()
    assert version is not None
