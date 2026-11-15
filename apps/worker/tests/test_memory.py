"""Droits, mémoire éditoriale prouvée, coûts."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import Engine, text

from primestone.distribution import DistributionService
from primestone.forensic import forensic_service
from primestone.governance import FOUNDER, GovernanceError, GovernanceService
from primestone.memory import MemoryService, MemoryServiceError, panel_citations
from primestone.storytelling import StorytellingService

pytestmark = pytest.mark.integration
SCRIPT = (
    "00:00 - Mystère\nDespair sourit [Sandman 1, p. 12, case 3]. "
    "Le décor change [Sandman 1, p. 13].\n"
)


def test_panel_citations_need_rights_before_production(db_engine: Engine) -> None:
    assert [c["panel"] for c in panel_citations(SCRIPT)] == [3]  # p. 13 : source, pas une case
    memory, gov = MemoryService(db_engine), GovernanceService(db_engine)
    dist = DistributionService(db_engine)
    stories = StorytellingService(db_engine, forensic_service(db_engine))
    script_id = stories.create(title="Despair", language="fr", content=SCRIPT, author="moi")
    with db_engine.begin() as conn:
        conn.execute(text("UPDATE script SET status = 'VALIDATED' WHERE id = :s"), {"s": script_id})
    assert not memory.rights_check(script_id)["complete"]
    channel = dist.add_channel(platform="YOUTUBE", language="fr", handle="@p", name="FR")
    item = dist.propose(
        channel_id=channel, title="Despair", proposed_by="agent", script_id=script_id
    )
    with pytest.raises(GovernanceError, match="droits manquants"):
        gov.approve(item["decision_id"], decided_by="moi", role=FOUNDER)
    with pytest.raises(MemoryServiceError, match="page et la case"):
        memory.record_rights(
            kind="PANEL_QUOTE",
            subject="case",
            source="DC",
            basis="QUOTATION",
            proof="analyse",
            limits="courte",
            recorded_by="moi",
        )
    expired = memory.record_rights(
        kind="PANEL_QUOTE",
        subject="Despair sourit",
        source="Sandman 1, DC",
        basis="QUOTATION",
        proof="citation illustrant l'analyse",
        limits="une case, durée courte",
        recorded_by="moi",
        document_title="Sandman 1",
        page_number=12,
        panel_number=3,
        expires_on=date(2020, 1, 1),
    )
    assert memory.rights()[0]["expired"] is True
    assert not memory.rights_check(script_id)["complete"]
    memory.withdraw_rights(expired)
    memory.record_rights(
        kind="PANEL_QUOTE",
        subject="Despair sourit",
        source="Sandman 1, DC",
        basis="QUOTATION",
        proof="citation illustrant l'analyse",
        limits="une case, durée courte",
        recorded_by="moi",
        document_title="sandman 1",
        page_number=12,
        panel_number=3,
    )
    assert memory.rights_check(script_id)["complete"]
    gov.approve(item["decision_id"], decided_by="moi", role=FOUNDER)


def test_lessons_only_from_proof(db_engine: Engine) -> None:
    memory = MemoryService(db_engine)
    with db_engine.begin() as conn:
        content_id = conn.execute(
            text(
                "INSERT INTO content_item (platform, external_id, title) "
                "VALUES ('YOUTUBE', 'v1', 'Despair') RETURNING id"
            )
        ).scalar_one()
        planned = conn.execute(
            text(
                "INSERT INTO experiment (title, hypothesis, variable, metric, author) "
                "VALUES ('T', 'H', 'TITLE', 'ctr', 'moi') RETURNING id"
            )
        ).scalar_one()
    with pytest.raises(MemoryServiceError, match="aucune statistique"):
        memory.record_lesson("x", source_type="content_item", source_id=content_id, recorded_by="a")
    with pytest.raises(MemoryServiceError, match="pas démontré"):
        memory.record_lesson("x", source_type="experiment", source_id=planned, recorded_by="a")
    with db_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO performance_metric (content_id, metric, value, source, data_class, "
                "imported_by) VALUES (:c, 'avg_view_percentage', 41, 'MANUAL', "
                "'PRIVATE_AUTHORIZED', 'moi')"
            ),
            {"c": content_id},
        )
        conn.execute(
            text(
                "UPDATE experiment SET status = 'CONCLUDED', "
                'result = \'{"winner": "B", "p_value": 0.01}\' WHERE id = :e'
            ),
            {"e": planned},
        )
    observed = memory.record_lesson(
        "Rétention 41 % sur Despair",
        source_type="content_item",
        source_id=content_id,
        recorded_by="moi",
    )
    demonstrated = memory.record_lesson(
        "Le titre B l'emporte", source_type="experiment", source_id=planned, recorded_by="moi"
    )
    assert observed["evidence_level"] == "OBSERVED"
    assert demonstrated["evidence_level"] == "DEMONSTRATED"
    memory.retract_lesson(observed["lesson_id"], reason="mesure corrigée")
    statuses = {lesson["lesson"]: lesson["status"] for lesson in memory.lessons()}
    assert statuses["Rétention 41 % sur Despair"] == "RETRACTED"
    assert {e["kind"] for e in memory.journal()} == {"lesson"}

    costs = memory.costs()
    assert costs["zero_cost_mode"] is True
    assert costs["total_usd"] == 0
