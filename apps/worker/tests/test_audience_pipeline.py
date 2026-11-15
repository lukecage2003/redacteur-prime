"""Audience de bout en bout : segments prouvés, graphe d'audience, communauté anonymisée."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import Engine, text

from primestone.audience import AudienceError, AudienceService
from primestone.editorial import EditorialService
from primestone.forensic import forensic_service
from primestone.jobs import PostgresJobQueue
from primestone.knowledge import KnowledgeService

pytestmark = pytest.mark.integration


def test_segments_need_two_observed_evidence_kinds(db_engine: Engine) -> None:
    audience = AudienceService(db_engine)
    with pytest.raises(AudienceError, match="âge"):
        audience.create_segment(
            name="18-24 ans", description="d", motivations=["x"], knowledge_level=None, author="moi"
        )
    with pytest.raises(AudienceError, match="motivation"):
        audience.create_segment(
            name="Vide", description="d", motivations=[], knowledge_level=None, author="moi"
        )
    seg = audience.create_segment(
        name="Curieux du cosmique",
        description="Veut comprendre les entités abstraites de Marvel et DC",
        motivations=["comprendre la cosmologie", "relier les univers"],
        knowledge_level="INTERMEDIATE",
        author="moi",
    )
    declared = audience.add_evidence(
        seg, kind="DECLARED", statement="intuition", data={}, data_class="PUBLIC", author="moi"
    )
    assert declared["status"] == "HYPOTHESIS"
    with pytest.raises(AudienceError, match="données"):
        audience.add_evidence(
            seg,
            kind="METRIC",
            statement="x",
            data={},
            data_class="PRIVATE_AUTHORIZED",
            author="moi",
        )
    metric = audience.add_evidence(
        seg,
        kind="METRIC",
        statement="Rétention 52 % sur les vidéos cosmiques",
        data={"avg_view_percentage": 52, "videos": 6},
        data_class="PRIVATE_AUTHORIZED",
        author="moi",
    )
    assert metric["status"] == "HYPOTHESIS"  # une seule nature observée
    cluster = audience.add_evidence(
        seg,
        kind="COMMENT_CLUSTER",
        statement="14 questions sur les Endless",
        data={"count": 14},
        data_class="PUBLIC",
        author="moi",
    )
    assert cluster["status"] == "CONFIRMED"
    with db_engine.begin() as conn:
        topic = conn.execute(
            text(
                "INSERT INTO market_topic (name, keywords_fr, keywords_en, author) VALUES "
                "('Endless', '[\"endless\"]', '[\"endless\"]', 'moi') RETURNING id"
            )
        ).scalar_one()
    audience.link(
        seg,
        target_kind="TOPIC",
        target=str(topic),
        relation="ASKS_ABOUT",
        evidence_id=cluster["evidence_id"],
    )
    other = audience.create_segment(
        name="Autre", description="d", motivations=["m"], knowledge_level=None, author="moi"
    )
    with pytest.raises(AudienceError, match="segment"):
        audience.link(
            other,
            target_kind="TOPIC",
            target=str(topic),
            relation="ASKS_ABOUT",
            evidence_id=cluster["evidence_id"],
        )
    [confirmed] = [s for s in audience.segments() if s["name"] == "Curieux du cosmique"]
    assert confirmed["status"] == "CONFIRMED"
    assert confirmed["links"][0]["label"] == "Endless"
    assert audience.retract_evidence(cluster["evidence_id"]) == "HYPOTHESIS"


def test_community_and_audience_brief(db_engine: Engine) -> None:
    audience = AudienceService(db_engine)
    stored = audience.import_comments(
        [
            {"external_id": f"c{i}", "text": f"Pourquoi Despair fait ça ? {i}", "like_count": 1}
            for i in range(3)
        ]
        + [
            {"external_id": "c9", "text": "Fais une vidéo sur Morpheus"},
            {"external_id": "c0", "text": " "},
        ],
        platform="youtube",
    )
    assert stored == {"received": 5, "stored": 4}
    assert (
        audience.import_comments([{"external_id": "c1", "text": "doublon"}], platform="youtube")[
            "stored"
        ]
        == 0
    )
    report = audience.community()
    assert report["by_kind"] == {"QUESTION": 3, "REQUEST": 1}
    assert report["recurring"][0]["kind"] == "QUESTION"

    forensic = forensic_service(db_engine)
    editorial = EditorialService(
        db_engine,
        forensic,
        KnowledgeService(db_engine, forensic),
        PostgresJobQueue(db_engine),
        audience=audience,
    )
    mission_id = editorial.create_mission("AUDIENCE_BRIEF", [], {})
    asyncio.run(editorial.run_mission({"mission_id": str(mission_id)}))
    result = editorial.mission(mission_id)["result"]
    assert result["deliverable"].startswith("# Note d'audience")
    assert result["recommendation"] == "NE PAS VALIDER"  # aucun segment confirmé
