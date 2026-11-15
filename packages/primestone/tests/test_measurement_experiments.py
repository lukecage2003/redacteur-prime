from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from primestone.performance import (
    OAuthError,
    access_token_provider,
    consent_url,
    decide,
    evaluate,
    wilson,
)


def variant(label: str, n: int | None, s: int | None, share: float | None = None) -> dict:
    return {
        "label": label,
        "exposures": n,
        "successes": s,
        "reported_share": share,
        "source": "MANUAL",
    }


def test_winner_only_with_enough_data_and_significance() -> None:
    clear = decide([variant("A", 20_000, 1_200), variant("B", 20_000, 900)])
    assert (clear["status"], clear["winner"]) == ("CONCLUDED", "A")
    assert clear["p_value"] < 0.05
    assert clear["relative_lift"] == pytest.approx(1 / 3, abs=1e-3)
    small = decide([variant("A", 200, 20), variant("B", 200, 5)])
    assert (small["status"], small["winner"]) == ("INCONCLUSIVE", None)
    assert "insuffisant" in small["reason"]
    close = decide([variant("A", 20_000, 1_000), variant("B", 20_000, 990)])
    assert close["status"] == "INCONCLUSIVE"
    assert "non significative" in close["reason"]


def test_platform_share_is_never_a_demonstration() -> None:
    result = decide([variant("A", None, None, 0.62), variant("B", None, None, 0.38)])
    assert result["status"] == "INCONCLUSIVE"
    assert len(result["platform_reported"]) == 2
    assert "non démontrée" in result["reason"]


def test_wilson_interval() -> None:
    low, high = wilson(50, 1000)
    assert low < 0.05 < high
    assert wilson(0, 0) == (0.0, 0.0)


def content(cid: str, objective: str | None, **metrics: float) -> dict:
    return {"id": cid, "title": cid, "objective": objective, "format": "LONG", "metrics": metrics}


def test_evaluation_by_objective_not_by_views() -> None:
    contents = [
        content("d1", "DISCOVERY", ctr=8.0, views=100),
        content("d2", "DISCOVERY", ctr=5.0, views=90_000),
        content("d3", "DISCOVERY", ctr=5.0, views=80_000),
        content("c1", "COMMUNITY", comments=300),
        content("x", None, views=1),
    ]
    report = evaluate(contents)
    d1 = next(e for e in report["evaluations"] if e["id"] == "d1")
    assert d1["kpis"]["ctr"]["status"] == "AU-DESSUS"  # peu de vues, mais objectif atteint
    assert "views" not in d1["kpis"]
    assert d1["kpis"]["new_viewers"]["status"] == "NON FOURNI"  # jamais estimé
    c1 = next(e for e in report["evaluations"] if e["id"] == "c1")
    assert c1["kpis"]["comments"]["status"] == "REPÈRE INSUFFISANT"
    assert report["unclassified"] == ["x"]


def test_oauth_consent_and_refresh() -> None:
    url, state = consent_url("client", "http://127.0.0.1:8765")
    query = parse_qs(urlparse(url).query)
    assert query["access_type"] == ["offline"]
    assert "yt-analytics.readonly" in query["scope"][0]
    assert query["state"] == [state]
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"access_token": "A1", "expires_in": 3600})

    token = access_token_provider("c", "s", "r", transport=httpx.MockTransport(handler))
    assert token() == token() == "A1"
    assert len(calls) == 1  # mis en cache
    denied = access_token_provider(
        "c", "s", "r", transport=httpx.MockTransport(lambda r: httpx.Response(400))
    )
    with pytest.raises(OAuthError):
        denied()
