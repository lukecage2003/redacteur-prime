"""Creative de bout en bout : charte versionnée, séries, packaging à partir d'un script évalué."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import Engine

from primestone.creative import DEFAULT_CHARTER, CreativeError, CreativeService
from primestone.editorial import EditorialService
from primestone.forensic import forensic_service
from primestone.governance import FOUNDER, GovernanceError, GovernanceService
from primestone.jobs import PostgresJobQueue
from primestone.knowledge import KnowledgeService
from primestone.storytelling import StorytellingService

pytestmark = pytest.mark.integration
SCRIPT = (
    "00:00 - Mystère\nEt si Despair avait tout prévu ? Personne ne le remarque.\n"
    "01:00 - Indices\nMais pourquoi Superman ? Vous allez voir.\n"
    "02:00 - Conclusion\nEn résumé, l'espoir gagne. Et vous ?"
)


def test_charter_series_packaging(db_engine: Engine) -> None:
    async def writer(subject: str, script: str) -> list[str]:
        return ["Despair : le plan secret", "Batman explique tout"]

    creative = CreativeService(db_engine, writer)
    assert creative.charter()["version"] == 0  # charte par défaut, à personnaliser
    with pytest.raises(CreativeError, match="incomplète"):
        creative.publish_charter({"colors": []}, name="x", author="moi", note=None)
    assert (
        creative.publish_charter(DEFAULT_CHARTER, name="Primestone v1", author="moi", note="départ")
        == 1
    )
    assert (
        creative.publish_charter(DEFAULT_CHARTER, name="Primestone v2", author="moi", note=None)
        == 2
    )
    # Brouillons : rien ne s'applique sans le fondateur (ADR-0027).
    assert creative.charter()["version"] == 0
    governance = GovernanceService(db_engine)
    pending = governance.decisions("PROPOSED")
    assert [d["proposal"]["charter_version"] for d in pending] == [2, 1]
    with pytest.raises(GovernanceError, match="fondateur"):
        governance.approve(pending[0]["id"], decided_by="chief_editor", role="AGENT")
    for decision in reversed(pending):
        governance.approve(decision["id"], decided_by="moi", role=FOUNDER)
    assert creative.charter()["version"] == 2

    stories = StorytellingService(db_engine, forensic_service(db_engine))
    script_id = stories.create(title="Despair", language="fr", content=SCRIPT, author="moi")
    with pytest.raises(CreativeError, match="évaluer"):
        asyncio.run(creative.package(script_id))
    stories.evaluate(script_id)
    result = asyncio.run(creative.package(script_id))
    assert result["charter_version"] == 2
    titles = {t["title"]: t for t in result["titles"]}
    assert titles["Despair : le plan secret"]["honest"] is True
    assert titles["Batman explique tout"]["honest"] is False  # Batman absent du script
    assert creative.packagings(script_id)[0]["charter_version"] == 2

    series_id = creative.create_series(
        name="Les Endless décryptés",
        promise="Un Endless expliqué preuves à l'appui",
        identity="enquête sobre",
        tone="curieux",
        structure=["Mystère", "Indices", "Conclusion"],
        target_minutes=2,
        art_direction="charte v2",
        distribution=["YouTube long", "Shorts"],
        evolution="un Endless par épisode",
        author="moi",
    )
    # Brouillon : aucun épisode tant que le fondateur n'a pas ouvert l'émission au test.
    with pytest.raises(CreativeError, match="DRAFT"):
        creative.add_episode(series_id, script_id)
    [opening] = governance.decisions("PROPOSED")
    assert opening["proposal"] == {"from": "DRAFT", "to": "TESTING"}
    governance.approve(opening["id"], decided_by="moi", role=FOUNDER)
    assert creative.add_episode(series_id, script_id) == 1
    with pytest.raises(CreativeError, match="déjà"):
        creative.add_episode(series_id, script_id)
    [series] = creative.series()
    assert series["episodes"][0]["title"] == "Despair"
    # Le script de test dure ~12 s pour une cible de 2 min : l'écart est signalé.
    assert series["consistency"][0].startswith("épisode 1 : 0 min pour une cible de 2")

    forensic = forensic_service(db_engine)
    editorial = EditorialService(
        db_engine,
        forensic,
        KnowledgeService(db_engine, forensic),
        PostgresJobQueue(db_engine),
        storytelling=stories,
        creative=creative,
    )
    mission_id = editorial.create_mission("PACKAGING_REVIEW", [], {"script_id": str(script_id)})
    asyncio.run(editorial.run_mission({"mission_id": str(mission_id)}))
    mission = editorial.mission(mission_id)
    assert mission["title"] == "Packaging : Despair"
    assert mission["result"]["deliverable"].startswith("# Packaging : Despair")
    assert mission["result"]["fact_check"]["verdict"] != "FAIL"
