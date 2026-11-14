"""Market Intelligence de bout en bout sur PostgreSQL (coût nul, aucun réseau)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from primestone.market import MarketError, MarketService, YouTubeClient

pytestmark = pytest.mark.integration

FICHE = {"access": "public", "quota": "aucun", "terms_url": "https://ex.test/terms"}


def youtube(views: int, calls: list[str]) -> YouTubeClient:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path.endswith("/search"):
            return httpx.Response(200, json={"items": [{"id": {"videoId": "yt1"}}]})
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "yt1",
                        "snippet": {
                            "title": "Sandman explained",
                            "publishedAt": "2026-11-01T00:00:00Z",
                        },
                        "statistics": {"viewCount": str(views)},
                    }
                ]
            },
        )

    return YouTubeClient("k", transport=httpx.MockTransport(handler))


def test_sources_require_a_verified_fiche(db_engine: Engine) -> None:
    market = MarketService(db_engine)
    market.register_source(key="manuel", name="Relevés", kind="MANUAL", **FICHE)
    with pytest.raises(MarketError, match="non validée"):
        market.import_records("manuel", [], author="moi")
    with pytest.raises(MarketError, match="déjà"):
        market.register_source(key="manuel", name="x", kind="MANUAL", **FICHE)
    with pytest.raises(MarketError, match="incomplète"):
        market.register_source(
            key="x", name="x", kind="MANUAL", access="", quota="q", terms_url="t"
        )
    with pytest.raises(MarketError, match="HTTPS"):
        market.register_source(key="r", name="r", kind="RSS", **FICHE, config={"url": "http://a"})
    market.verify_source("manuel", author="moi")
    [source] = market.sources()
    assert (source["verified_by"], source["data_class"]) == ("moi", "PUBLIC")
    with pytest.raises(LookupError):
        market.verify_source("inconnue", author="moi")


def test_manual_import_public_only_and_snapshots(db_engine: Engine) -> None:
    market = MarketService(db_engine)
    market.register_source(key="manuel", name="Relevés", kind="MANUAL", **FICHE)
    market.verify_source("manuel", author="moi")
    row = {
        "platform": "YouTube",
        "external_id": "abc",
        "title": "Sandman expliqué",
        "language": "fr",
        "observed_at": "2026-11-10T12:00:00+00:00",
        "published_at": "2026-11-01T00:00:00+00:00",
        "views": "1500",
    }
    first = market.import_records("manuel", [row], author="moi")
    assert (first["new_items"], first["metrics"]) == (1, 1)
    again = market.import_records("manuel", [row], author="moi")  # idempotent
    assert (again["new_items"], again["metrics"]) == (0, 0)
    later = market.import_records(
        "manuel", [{**row, "observed_at": "2026-11-12T12:00:00+00:00", "views": 2000}], author="moi"
    )
    assert later["metrics"] == 1  # nouvel instantané, l'ancien est conservé
    with pytest.raises(MarketError, match="privée"):
        market.import_records("manuel", [{**row, "ctr": "4.2"}], author="moi")
    with pytest.raises(MarketError, match="fuseau"):
        market.import_records(
            "manuel", [{**row, "observed_at": "2026-11-10T12:00:00"}], author="moi"
        )
    with pytest.raises(MarketError, match="title"):
        market.import_records("manuel", [{**row, "title": " "}], author="moi")
    with db_engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM market_metric")).scalar_one() == 2
        with pytest.raises(IntegrityError, match="ck_market_metric_metric"):
            conn.execute(
                text(
                    "INSERT INTO market_metric (item_id, collection_id, metric, value, "
                    "data_class, observed_at) SELECT item_id, collection_id, 'retention', 1, "
                    "'PUBLIC', now() FROM market_metric LIMIT 1"
                )
            )


def test_youtube_collection_respects_free_quota(db_engine: Engine) -> None:
    calls: list[str] = []
    market = MarketService(db_engine, youtube=lambda: youtube(5000, calls), youtube_daily_quota=250)
    market.register_source(key="yt", name="YouTube", kind="YOUTUBE_API", **FICHE)
    market.verify_source("yt", author="moi")
    result = market.collect_youtube("yt", "sandman", language="en")
    assert (result["new_items"], result["metrics"], result["quota_units"]) == (1, 1, 101)
    market.collect_youtube("yt", "sandman", language="en")
    assert market.quota_used_today() == 202
    with pytest.raises(MarketError, match="quota"):
        market.collect_youtube("yt", "sandman", language="en")
    assert len(calls) == 4  # le 3ᵉ appel n'a jamais atteint l'API
    refreshed = market.refresh_youtube("yt")
    assert refreshed["quota_units"] == 1
    without_key = MarketService(db_engine)
    with pytest.raises(MarketError, match="non configurée"):
        without_key.collect_youtube("yt", "sandman", language="fr")


def test_failed_collection_is_traced(db_engine: Engine) -> None:
    market = MarketService(db_engine, fetch_feed=lambda _url: b"<rss>")
    market.register_source(
        key="rss",
        name="Flux",
        kind="RSS",
        language="fr",
        config={"url": "https://ex.test/f"},
        **FICHE,
    )
    market.verify_source("rss", author="moi")
    with pytest.raises(MarketError, match="illisible"):
        market.collect_rss("rss")
    [failed] = market.collections()
    assert (failed["status"], failed["source"]) == ("FAILED", "rss")


def test_analysis_end_to_end(db_engine: Engine) -> None:
    market = MarketService(db_engine)
    market.register_source(key="manuel", name="Relevés", kind="MANUAL", **FICHE)
    market.verify_source("manuel", author="moi")
    now = datetime.now(UTC)
    rows = [
        {
            "platform": "youtube",
            "external_id": f"{lang}{i}",
            "title": title,
            "language": lang,
            "observed_at": now.isoformat(),
            "published_at": (now - timedelta(days=5)).isoformat(),
            "views": views,
        }
        for lang, title, views, n in (
            ("en", "Sandman explained", 80_000, 6),
            ("fr", "Sandman expliqué", 3_000, 1),
        )
        for i in range(n)
    ]
    market.import_records("manuel", rows, author="moi")
    market.add_topic("Sandman", keywords_fr=["sandman"], keywords_en=["sandman"], author="moi")
    with pytest.raises(MarketError, match="déjà"):
        market.add_topic("Sandman", keywords_fr=["x"], keywords_en=[], author="moi")
    result = market.analysis(min_items=5)
    [row] = result["topics"]
    assert row["status"] == "SCORED"
    assert row["saturation_fr"] == round(1 / 6, 3)
    assert result["opportunities"] == ["Sandman"]


def test_market_brief_mission(db_engine: Engine) -> None:
    import asyncio

    from primestone.editorial import EditorialService
    from primestone.forensic import forensic_service
    from primestone.jobs import PostgresJobQueue
    from primestone.knowledge import KnowledgeService

    market = MarketService(db_engine)
    forensic = forensic_service(db_engine)
    editorial = EditorialService(
        db_engine,
        forensic,
        KnowledgeService(db_engine, forensic),
        PostgresJobQueue(db_engine),
        market=market,
    )
    market.add_topic("Sandman", keywords_fr=["sandman"], keywords_en=["sandman"], author="moi")
    empty = editorial.create_mission("MARKET_BRIEF", [], {})
    asyncio.run(editorial.run_mission({"mission_id": str(empty)}))
    assert editorial.mission(empty)["result"]["recommendation"] == "NE PAS VALIDER"

    market.register_source(key="manuel", name="Relevés", kind="MANUAL", **FICHE)
    market.verify_source("manuel", author="moi")
    now = datetime.now(UTC).isoformat()
    market.import_records(
        "manuel",
        [
            {
                "platform": "youtube",
                "external_id": f"e{i}",
                "title": "Sandman explained",
                "language": "en",
                "observed_at": now,
                "views": 10_000 + i,
                "url": f"https://ex.test/{i}",
            }
            for i in range(5)
        ],
        author="moi",
    )
    mission_id = editorial.create_mission("MARKET_BRIEF", [], {"min_items": 5})
    asyncio.run(editorial.run_mission({"mission_id": str(mission_id)}))
    mission = editorial.mission(mission_id)
    result = mission["result"]
    assert mission["status"] == "AWAITING_APPROVAL"
    assert result["recommendation"] == "VALIDER AVEC RÉSERVES"
    assert result["fact_check"]["verdict"] == "NOT_APPLICABLE"
    brief = result["deliverable"]
    assert brief.startswith("# Note de marché : écarts EN → FR")
    assert "Sandman : écart 1.0" in brief
    assert "Opportunités : Sandman." in brief
    assert "source publique : Sandman explained (10004 vues" in brief
    assert {r["provider"] for r in mission["agent_runs"]} == {"deterministe"}
