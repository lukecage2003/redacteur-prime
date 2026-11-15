"""Performance de bout en bout (coût nul) : import Studio, liaison au script, bilan."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from primestone.editorial import EditorialService
from primestone.forensic import forensic_service
from primestone.jobs import PostgresJobQueue
from primestone.knowledge import KnowledgeService
from primestone.performance import PerformanceService
from primestone.storytelling import StorytellingService

pytestmark = pytest.mark.integration

SCRIPT = "00:00 - Intro\nEt si tout était faux ? Personne ne le voit.\n01:00 - Fin\nEn résumé, oui."


def test_performance_loop(db_engine: Engine) -> None:
    forensic = forensic_service(db_engine)
    stories = StorytellingService(db_engine, forensic)
    perf = PerformanceService(db_engine)
    rows = "\n".join(
        f"v{i},Vidéo {i},,{1000 * (i + 1)},,{30 + i},{10000},{4 + i / 10},," for i in range(6)
    )
    header = (
        "Content,Video title,Video publish time,Views,Average view duration,"
        "Average percentage viewed (%),Impressions,Impressions click-through rate (%),"
        "Watch time (hours),Subscribers\n"
    )
    result = perf.import_studio_csv(header + rows, author="moi")
    assert (result["new_contents"], result["ignored_columns"]) == (6, [])
    assert perf.import_studio_csv(header + rows, author="moi")["new_contents"] == 0  # instantané
    contents = perf.contents()
    for i, content in enumerate(sorted(contents, key=lambda c: c["title"])):
        script_id = stories.create(
            title=f"S{i}", language="fr", content=SCRIPT + " ?" * i, author="moi"
        )
        stories.evaluate(script_id)
        perf.link_script(content["id"], script_id, language="fr")
    report = perf.report(min_items=5)
    assert report["status"] == "OK"
    assert report["linked_to_scored_script"] == 6
    assert report["benchmarks"]["views"] == 3500.0
    assert report["data_class"] == "PRIVATE_AUTHORIZED"
    with db_engine.connect() as conn, pytest.raises(IntegrityError, match="ck_performance_metric"):
        conn.execute(
            text(
                "INSERT INTO performance_metric (content_id, metric, value, source, data_class, "
                "imported_by) SELECT id, 'views', 1, 'MANUAL', 'PUBLIC', 'x' "
                "FROM content_item LIMIT 1"
            )
        )

    editorial = EditorialService(
        db_engine,
        forensic,
        KnowledgeService(db_engine, forensic),
        PostgresJobQueue(db_engine),
        performance=perf,
    )
    mission_id = editorial.create_mission("PERFORMANCE_REVIEW", [], {})
    asyncio.run(editorial.run_mission({"mission_id": str(mission_id)}))
    mission = editorial.mission(mission_id)
    assert mission["result"]["recommendation"] == "VALIDER AVEC RÉSERVES"
    assert mission["result"]["deliverable"].startswith("# Bilan de performance de la chaîne")
