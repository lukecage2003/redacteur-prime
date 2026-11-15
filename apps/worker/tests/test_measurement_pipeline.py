"""Phase 14 de bout en bout : objectifs, synchronisation autorisée simulée, expériences."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import Engine

from primestone.performance import AnalyticsClient, PerformanceError, PerformanceService

pytestmark = pytest.mark.integration


def analytics() -> AnalyticsClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("dimensions") == "elapsedVideoTimeRatio":
            return httpx.Response(
                200, json={"rows": [[0.0, 1.0, 0.5], [0.5, 0.42, 0.5], [1.0, 0.2, None]]}
            )
        return httpx.Response(
            200,
            json={
                "columnHeaders": [
                    {"name": n} for n in ("video", "views", "shares", "subscribersLost")
                ],
                "rows": [["vid1", 900, 12, 1], ["vid2", 1500, 30, 0]],
            },
        )

    return AnalyticsClient(lambda: "T", transport=httpx.MockTransport(handler))


def test_measurement_and_experiments(db_engine: Engine) -> None:
    perf = PerformanceService(db_engine)
    result = perf.sync_analytics(analytics(), date(2026, 10, 1), date(2026, 10, 31), author="moi")
    assert (result["new_contents"], result["retention_points"]) == (2, 6)
    contents = {c["external_id"]: c for c in perf.contents()}
    assert contents["vid1"]["metrics"]["shares"] == 12.0
    curve = perf.retention(contents["vid1"]["id"])
    assert [p["elapsed_ratio"] for p in curve] == [0.0, 0.5, 1.0]

    perf.set_objective(contents["vid1"]["id"], objective="COMMUNITY", format_="LONG")
    with pytest.raises(PerformanceError, match="objectif"):
        perf.set_objective(contents["vid1"]["id"], objective="VIRAL", format_=None)
    report = perf.objective_report()
    assert [e["objective"] for e in report["evaluations"]] == ["COMMUNITY"]
    assert report["unclassified"] == ["vid2"]

    exp = perf.create_experiment(
        title="Miniature visage vs objet",
        hypothesis="Un visage expressif augmente le CTR des vidéos de découverte",
        variable="THUMBNAIL",
        metric="ctr",
        author="moi",
        audience="nouveaux spectateurs",
    )
    perf.add_variant(exp, label="A", description="visage", exposures=30_000, successes=1_800)
    perf.add_variant(exp, label="B", description="objet", exposures=30_000, successes=1_350)
    with pytest.raises(PerformanceError, match="ensemble"):
        perf.add_variant(exp, label="C", description="x", exposures=10)
    outcome = perf.conclude(exp, conclusion="Visage retenu", next_experiment="Tester le texte")
    assert (outcome["status"], outcome["winner"]) == ("CONCLUDED", "A")
    with pytest.raises(PerformanceError, match="close"):
        perf.add_variant(exp, label="D", description="x", reported_share=Decimal("0.5"))
    weak = perf.create_experiment(
        title="Titre question", hypothesis="h", variable="TITLE", metric="ctr", author="moi"
    )
    perf.add_variant(
        weak,
        label="A",
        description="q",
        reported_share=Decimal("0.55"),
        source="YOUTUBE_TEST_COMPARE",
    )
    perf.add_variant(
        weak,
        label="B",
        description="a",
        reported_share=Decimal("0.45"),
        source="YOUTUBE_TEST_COMPARE",
    )
    assert perf.conclude(weak, conclusion=None, next_experiment=None)["status"] == "INCONCLUSIVE"
    learned = perf.report(min_items=5)
    assert [d["winner"] for d in learned["demonstrated"]] == ["A"]
    assert {e["status"] for e in perf.experiments()} == {"CONCLUDED", "INCONCLUSIVE"}
