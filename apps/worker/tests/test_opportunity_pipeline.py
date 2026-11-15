"""Opportunités de bout en bout : marché + communauté + audience + laboratoire."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine

from primestone.audience import AudienceService
from primestone.editorial import EditorialService
from primestone.forensic import forensic_service
from primestone.jobs import PostgresJobQueue
from primestone.knowledge import KnowledgeService
from primestone.market import MarketService, OpportunityService

pytestmark = pytest.mark.integration
FICHE = {"access": "saisie", "quota": "aucun", "terms_url": "https://ex.test"}


def test_opportunities(db_engine: Engine) -> None:
    market = MarketService(db_engine)
    market.register_source(key="m", name="Relevés", kind="MANUAL", **FICHE)
    market.verify_source("m", author="moi")
    now = datetime.now(UTC).isoformat()
    rows = [
        {
            "platform": "youtube",
            "external_id": f"e{i}",
            "title": "Sandman explained",
            "language": "en",
            "observed_at": now,
            "views": 50_000 + i,
        }
        for i in range(5)
    ]
    rows += [
        {
            "platform": "youtube",
            "external_id": f"f{i}",
            "title": "Sandman expliqué",
            "language": "fr",
            "observed_at": now,
            "views": 8_000 + i,
            "channel": "Chaîne FR",
        }
        for i in range(5)
    ]
    rows += [
        {
            "platform": "youtube",
            "external_id": f"w{i}",
            "title": "Watchmen explained",
            "language": "en",
            "observed_at": now,
            "views": 30_000,
        }
        for i in range(5)
    ]
    market.import_records("m", rows, author="moi")
    market.add_topic("Sandman", keywords_fr=["sandman"], keywords_en=["sandman"], author="moi")
    market.add_topic("Watchmen", keywords_fr=["watchmen"], keywords_en=["watchmen"], author="moi")
    audience = AudienceService(db_engine)
    audience.import_comments(
        [{"external_id": f"c{i}", "text": f"Fais une vidéo sur Sandman stp {i}"} for i in range(4)],
        platform="youtube",
    )
    knowledge = KnowledgeService(db_engine, forensic_service(db_engine))
    engine = OpportunityService(db_engine, market, knowledge.embedder)
    report = engine.opportunities(min_items=5)
    by_topic = {o["topic"]: o for o in report["opportunities"]}
    sandman, watchmen = by_topic["Sandman"], by_topic["Watchmen"]
    assert sandman["status"] == "OPPORTUNITY"  # vues FR mesurées + demandes
    assert sandman["need"][0].startswith("4 demande(s)")
    assert sandman["competition"]["fr_channels"] == ["Chaîne FR"]
    assert watchmen["status"] == "HYPOTHESIS"  # popularité EN seule
    assert report["opportunities"][0]["topic"] == "Sandman"

    forensic = forensic_service(db_engine)
    editorial = EditorialService(
        db_engine, forensic, knowledge, PostgresJobQueue(db_engine), opportunities=engine
    )
    mission_id = editorial.create_mission("OPPORTUNITY_BRIEF", [], {})
    asyncio.run(editorial.run_mission({"mission_id": str(mission_id)}))
    result = editorial.mission(mission_id)["result"]
    assert result["deliverable"].startswith("# Opportunités éditoriales")
    assert "## Sandman — OPPORTUNITY" in result["deliverable"]
    assert result["recommendation"] == "VALIDER AVEC RÉSERVES"
