from datetime import date
from decimal import Decimal

import httpx
import pytest

from primestone.performance import AnalyticsClient, ImportError_, learn, parse_studio_csv, spearman

CSV_FR = (
    "﻿Contenu,Titre de la vidéo,Heure de publication de la vidéo,Vues,"
    "Durée moyenne de visionnage,Pourcentage moyen regardé (%),Impressions,"
    "Taux de clics des impressions (%),Durée de visionnage (heures),Revenus estimés\n"
    "Total,,,3000,,,,,,\n"
    'abc123,Despair expliqué,"Nov 3, 2026","1 200",0:04:05,"41,5",20000,"6,1","81,7",12\n'
    "def456,Sandman,,1800,3:10,38.0,25000,5.2,95.0,\n"
)


def test_parse_studio_csv_french_headers() -> None:
    parsed = parse_studio_csv(CSV_FR)
    assert parsed["ignored_columns"] == ["Revenus estimés"]  # inconnue : ignorée, signalée
    first, second = parsed["rows"]  # la ligne « Total » est écartée
    assert first["external_id"] == "abc123"
    assert first["published_on"] == date(2026, 11, 3)
    m = first["metrics"]
    assert m["views"] == 1200
    assert m["avg_view_duration_s"] == 245
    assert m["avg_view_percentage"] == Decimal("41.5")
    assert m["ctr"] == Decimal("6.1")
    assert m["watch_time_min"] == Decimal("81.7") * 60
    assert second["metrics"]["avg_view_duration_s"] == 190
    with pytest.raises(ImportError_, match="identifiant"):
        parse_studio_csv("Titre,Vues\nx,1\n")


def test_analytics_client_maps_metrics_and_hides_token() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "columnHeaders": [
                    {"name": "video"},
                    {"name": "views"},
                    {"name": "averageViewPercentage"},
                ],
                "rows": [["abc123", 1500, 44.2]],
            },
        )

    client = AnalyticsClient(lambda: "TOKEN", transport=httpx.MockTransport(handler))
    [row] = client.video_report(date(2026, 10, 1), date(2026, 10, 31))
    assert row["metrics"] == {"views": Decimal("1500"), "avg_view_percentage": Decimal("44.2")}
    assert seen[0].url.params["ids"] == "channel==MINE"
    assert seen[0].headers["authorization"] == "Bearer TOKEN"
    denied = AnalyticsClient(
        lambda: "TOKEN", transport=httpx.MockTransport(lambda r: httpx.Response(401))
    )
    with pytest.raises(ImportError_) as err:
        denied.video_report(date(2026, 10, 1), date(2026, 10, 2))
    assert "TOKEN" not in str(err.value)


def test_spearman() -> None:
    assert spearman([1, 2, 3, 4], [10, 20, 30, 40]) == 1.0
    assert spearman([1, 2, 3, 4], [4, 3, 2, 1]) == -1.0
    assert spearman([1, 1, 1], [1, 2, 3]) is None
    assert spearman([1, 2], [1, 2]) is None


def test_learn_requires_enough_linked_contents() -> None:
    contents = [
        {
            "title": f"v{i}",
            "metrics": {"avg_view_percentage": 30 + i * 3, "ctr": 5.0},
            "script_criteria": {"hook": 5 + i, "writing": 10.0},
        }
        for i in range(6)
    ]
    report = learn(contents, min_items=5)
    assert report["status"] == "OK"
    top = report["signals"][0]
    assert (top["criterion"], top["target"], top["rho"]) == ("hook", "avg_view_percentage", 1.0)
    assert any("hook" in r and "signal, pas preuve" in r for r in report["recommendations"])
    assert report["benchmarks"]["ctr"] == 5.0
    thin = learn(contents[:3], min_items=5)
    assert thin["status"] == "INSUFFICIENT_DATA"
    assert thin["signals"] == []
