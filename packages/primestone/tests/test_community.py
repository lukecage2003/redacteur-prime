import httpx
import pytest

from primestone.audience import YouTubeComments, classify, insights
from primestone.market import ConnectorError


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("Pourquoi Despair aide Superman ?", "QUESTION"),
        ("Fais une vidéo sur Morpheus stp", "REQUEST"),
        ("Ma théorie : Desire manipule tout", "THEORY"),
        ("C'est faux, il n'est pas mort", "CONTROVERSY"),
        ("Merci, super vidéo", "PRAISE"),
        ("ok", "OTHER"),
    ],
)
def test_classify(text: str, kind: str) -> None:
    assert classify(text) == kind


def test_insights_recurring_and_proposals_only() -> None:
    comments = [
        {"text": f"Pourquoi Despair aide Superman ? ({i})", "kind": "QUESTION", "like_count": i}
        for i in range(4)
    ]
    comments += [{"text": "Ma théorie sur Desire", "kind": "THEORY", "like_count": 0}] * 2
    report = insights(comments, known_names=["Despair", "Superman"])
    subjects = {(g["kind"], g["subject"]) for g in report["recurring"]}
    assert ("QUESTION", "Despair") in subjects
    assert all(g["count"] >= 3 for g in report["recurring"])  # 2 théories : pas récurrent
    assert any("Vidéo réponse" in p for p in report["proposals"])
    assert "aucune publication" in report["rule"]


def test_youtube_comments_strip_author_identity() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["videoId"] == "v1"
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "c1",
                        "snippet": {
                            "topLevelComment": {
                                "snippet": {
                                    "textOriginal": "Pourquoi ?",
                                    "likeCount": 3,
                                    "publishedAt": "2026-11-01T00:00:00Z",
                                    "authorDisplayName": "Pseudo",
                                    "authorChannelId": {"value": "UC123"},
                                }
                            }
                        },
                    }
                ]
            },
        )

    client = YouTubeComments("k", transport=httpx.MockTransport(handler))
    [comment] = client.threads("v1")
    assert comment["text"] == "Pourquoi ?"
    assert "Pseudo" not in str(comment)
    assert "UC123" not in str(comment)
    assert client.units == 1
    with pytest.raises(ConnectorError):
        YouTubeComments("")
