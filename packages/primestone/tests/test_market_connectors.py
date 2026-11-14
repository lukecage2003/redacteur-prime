import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from primestone.market import (
    ConnectorError,
    Item,
    Topic,
    YouTubeClient,
    analyze,
    fetch_feed,
    language_of,
    matches,
    parse_feed,
)

RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>Actus comics</title><language>fr-FR</language>
<item><title>Sandman : la série revient</title><link>https://ex.test/a</link>
<guid>a-1</guid><pubDate>Fri, 13 Nov 2026 10:00:00 GMT</pubDate></item>
<item><title></title><guid>vide</guid></item>
</channel></rss>"""

ATOM = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="en">
<entry><id>tag:x,1</id><title>Watchmen explained</title><link href="https://ex.test/w"/>
<updated>2026-11-01T08:00:00Z</updated><author><name>Chan</name></author></entry>
</feed>"""


def test_parse_rss_and_atom() -> None:
    [item] = parse_feed(RSS, language="en")
    assert (item["external_id"], item["language"], item["channel"]) == ("a-1", "fr", "Actus comics")
    assert item["published_at"] == datetime(2026, 11, 13, 10, tzinfo=UTC)
    assert item["metrics"] == {}
    [entry] = parse_feed(ATOM, language="fr")
    assert (entry["language"], entry["channel"], entry["url"]) == (
        "en",
        "Chan",
        "https://ex.test/w",
    )


def test_feed_refuses_entities_and_garbage() -> None:
    with pytest.raises(ConnectorError, match="DOCTYPE"):
        parse_feed('<!DOCTYPE x [<!ENTITY a "b">]><rss/>', language="en")
    with pytest.raises(ConnectorError, match="illisible"):
        parse_feed("pas du xml", language="en")
    with pytest.raises(ConnectorError, match="HTTPS"):
        fetch_feed("http://ex.test/rss", timeout=1)


def test_fetch_feed_status() -> None:
    ok = httpx.MockTransport(lambda r: httpx.Response(200, content=RSS.encode()))
    assert fetch_feed("https://ex.test/rss", timeout=1, transport=ok).startswith(b"<?xml")
    down = httpx.MockTransport(lambda r: httpx.Response(503))
    with pytest.raises(ConnectorError, match="503"):
        fetch_feed("https://ex.test/rss", timeout=1, transport=down)


def test_language_of() -> None:
    assert language_of("fr-CA", "en") == "fr"
    assert language_of("de", "en") == "en"
    assert language_of(None, "fr") == "fr"


def youtube_transport(seen: list[httpx.Request]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.endswith("/search"):
            return httpx.Response(
                200, json={"items": [{"id": {"videoId": "v1"}}, {"id": {"videoId": "v2"}}]}
            )
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "v1",
                        "snippet": {
                            "title": "Sandman expliqué",
                            "channelTitle": "Chaîne",
                            "publishedAt": "2026-10-01T00:00:00Z",
                            "defaultAudioLanguage": "fr",
                        },
                        "statistics": {"viewCount": "1200", "likeCount": "40"},
                    },
                    {
                        "id": "v2",
                        "snippet": {"title": "Sandman explained"},
                        "statistics": {"viewCount": "90000", "commentCount": "12"},
                    },
                ]
            },
        )

    return httpx.MockTransport(handler)


def test_youtube_client_public_metrics_and_quota() -> None:
    seen: list[httpx.Request] = []
    client = YouTubeClient("k", transport=youtube_transport(seen))
    records = client.search("sandman", language="en", max_results=80)
    assert client.units == 101  # search.list 100 + videos.list 1
    assert seen[0].url.params["maxResults"] == "50"
    assert seen[0].url.params["relevanceLanguage"] == "en"
    assert [r["language"] for r in records] == ["fr", "en"]
    assert records[0]["metrics"] == {"views": 1200, "likes": 40}  # masqué ≠ 0
    assert records[1]["metrics"] == {"views": 90000, "comments": 12}
    assert set().union(*(r["metrics"] for r in records)) <= {"views", "likes", "comments"}


def test_youtube_errors_never_leak_the_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": {"errors": [{"reason": "quotaExceeded"}]}})

    client = YouTubeClient("SECRET-KEY", transport=httpx.MockTransport(handler))
    with pytest.raises(ConnectorError) as err:
        client.search("x", language="fr")
    assert "quotaExceeded" in str(err.value)
    assert "SECRET-KEY" not in str(err.value)
    with pytest.raises(ConnectorError, match="absente"):
        YouTubeClient("")


NOW = datetime(2026, 11, 14, tzinfo=UTC)


def item(n: int, lang: str, title: str, views: int | None, days: int = 10) -> Item:
    return Item(
        id=f"{lang}{n}{title}",
        language=lang,
        title=title,
        description=None,
        url=f"https://ex.test/{n}",
        channel=None,
        published_at=NOW - timedelta(days=days),
        first_seen_at=NOW,
        views=views,
        observed_at=NOW,
    )


def test_matching_is_word_based_and_accent_insensitive() -> None:
    topic = Topic("t", "Sandman", ("sandman", "Rêve"))
    assert matches(topic, item(1, "fr", "Le seigneur du RÊVE", 1))
    assert not matches(topic, item(1, "en", "Sandmanesque", 1))


def test_gap_score_transparent_and_refuses_thin_data() -> None:
    sandman = Topic("s", "Sandman", ("sandman",))
    watchmen = Topic("w", "Watchmen", ("watchmen",))
    obscure = Topic("o", "Obscur", ("obscur",))
    items = (
        [item(i, "en", "Sandman explained", 100_000) for i in range(6)]
        + [item(i, "fr", "Sandman expliqué", 5_000) for i in range(2)]
        + [item(i, "en", "Watchmen review", 1_000) for i in range(5)]
        + [item(i, "fr", "Watchmen critique", 2_000) for i in range(5)]
        + [item(i, "en", "Obscur thing", 50) for i in range(3)]
        + [item(99, "en", "Sandman old", 10**9, days=400)]  # hors fenêtre
    )
    result = analyze(items, [sandman, watchmen, obscure], now=NOW, min_items=5)
    rows = {r["topic"]: r for r in result["topics"]}
    s, w, o = rows["Sandman"], rows["Watchmen"], rows["Obscur"]
    assert s["languages"]["en"]["items"] == 6  # l'ancien contenu est exclu
    assert (s["demand_en"], s["saturation_fr"]) == (1.0, round(2 / 6, 3))
    assert s["gap_score"] == round(1 - 2 / 6, 3)
    assert w["saturation_fr"] == 1.0
    assert w["gap_score"] == 0
    assert w["cultural_difference"] > 0  # Watchmen marche relativement mieux en français
    assert s["cultural_difference"] is None  # trop peu de contenus FR avec vues
    assert o["status"] == "INSUFFICIENT_DATA"
    assert o["gap_score"] is None
    assert result["opportunities"] == ["Sandman"]
    assert result["saturated_fr"] == ["Watchmen"]
    assert result["data_class"] == "ESTIMATE"
    assert all(src["data_class"] == "PUBLIC" for src in s["languages"]["en"]["sources"])
    assert any("log10" in line for line in s["explanation"])
    json.dumps(result, default=str)  # sérialisable pour l'API
