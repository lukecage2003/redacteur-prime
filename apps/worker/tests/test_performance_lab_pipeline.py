"""Content Performance Lab : autopsie, accroches, décrochages, boucle, validation."""

from __future__ import annotations

import asyncio
from datetime import date

import httpx
import pytest
from sqlalchemy import Engine

from primestone.audience import AudienceService
from primestone.editorial import EditorialService
from primestone.forensic import forensic_service
from primestone.jobs import PostgresJobQueue
from primestone.knowledge import KnowledgeService
from primestone.performance import AnalyticsClient, PerformanceLab, PerformanceService, hook_type
from primestone.storytelling import StorytellingService

pytestmark = pytest.mark.integration
SCRIPT = (
    "00:00 - Intro\nEt si Despair avait tout prévu ?\n"
    "01:00 - Suite\n" + "Le récit continue encore. " * 60 + "\n"
    "03:00 - Fin\nEn réalité, l'espoir gagne."
)


def analytics() -> AnalyticsClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("dimensions") == "elapsedVideoTimeRatio":
            return httpx.Response(
                200,
                json={
                    "rows": [
                        [0.0, 1.0, None],
                        [0.05, 0.8, None],
                        [0.5, 0.7, None],
                        [0.6, 0.4, None],
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "columnHeaders": [{"name": "video"}, {"name": "views"}],
                "rows": [["vid1", 1000]],
            },
        )

    return AnalyticsClient(lambda: "T", transport=httpx.MockTransport(handler))


def test_hook_type() -> None:
    assert hook_type("Et si tout était faux ?") == "QUESTION"
    assert hook_type("Il gagne, et pourtant il perd.") == "PARADOXE"
    assert hook_type("« Je suis l'espoir. » [T, p. 1]") == "CITATION"
    assert hook_type("Despair est une Endless.") == "AFFIRMATION"


def test_lab_end_to_end(db_engine: Engine) -> None:
    lab = PerformanceLab(db_engine)
    assert lab.validation()["demonstrated"] == 0  # base vide : rien de démontré
    perf = PerformanceService(db_engine)
    perf.sync_analytics(analytics(), date(2026, 10, 1), date(2026, 10, 31), author="moi")
    content_id = perf.contents()[0]["id"]
    stories = StorytellingService(db_engine, forensic_service(db_engine))
    script_id = stories.create(title="Despair", language="fr", content=SCRIPT, author="moi")
    stories.evaluate(script_id)
    perf.link_script(content_id, script_id, language="fr")
    perf.set_objective(content_id, objective="DISCOVERY", format_="LONG")
    AudienceService(db_engine).import_comments(
        [{"external_id": "q1", "text": "Pourquoi Despair ?"}],
        platform="youtube",
        content_id=content_id,
    )
    exp = perf.create_experiment(
        title="Titre",
        hypothesis="h",
        variable="TITLE",
        metric="ctr",
        author="moi",
        content_ids=[content_id],
    )
    perf.add_variant(exp, label="A", description="a", exposures=20_000, successes=1_400)
    perf.add_variant(exp, label="B", description="b", exposures=20_000, successes=1_000)
    perf.conclude(exp, conclusion=None, next_experiment=None)

    autopsy = lab.autopsy(content_id)
    evidence = {f["evidence"] for f in autopsy["findings"]}
    assert evidence == {"OBSERVED", "HYPOTHESIS", "DEMONSTRATED"}
    assert any(
        "décrochage" in f["finding"] and "Suite" in f["finding"] for f in autopsy["findings"]
    )
    assert autopsy["missing"] == []
    assert lab.hooks()["hooks"][0]["hook"] == "QUESTION"
    assert lab.drop_offs()["sections"][0]["section"] == "Suite"
    assert lab.returning()["evidence"] == "NON FOURNI"  # jamais estimé
    loop = lab.loop(script_id)
    assert loop["next"] == "RESEARCH"  # pas de comic relié : la recherche manque
    assert {s["step"] for s in loop["loop"] if s["done"]} >= {
        "SCRIPT",
        "PUBLISH",
        "MEASURE",
        "DIAGNOSE",
        "LEARN",
    }
    validation = lab.validation()
    assert 0 < validation["demonstrated"] < validation["total"]
    assert validation["complete"] is False

    forensic = forensic_service(db_engine)
    editorial = EditorialService(
        db_engine,
        forensic,
        KnowledgeService(db_engine, forensic),
        PostgresJobQueue(db_engine),
        performance=perf,
    )
    mission_id = editorial.create_mission("VIDEO_AUTOPSY", [], {"content_id": content_id})
    asyncio.run(editorial.run_mission({"mission_id": str(mission_id)}))
    result = editorial.mission(mission_id)["result"]
    assert result["deliverable"].startswith("# Autopsie : vid1")
    assert "[DEMONSTRATED]" in result["deliverable"]
