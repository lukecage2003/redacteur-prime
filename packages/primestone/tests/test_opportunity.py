from primestone.market import score_topic
from primestone.market.opportunity import build, formats_for


def test_missing_components_are_excluded_not_invented() -> None:
    only_gap = score_topic({"gap_score": 0.8})
    assert only_gap["score"] == 0.8
    assert only_gap["confidence"] == "LOW"
    assert set(only_gap["missing"]) == {
        "fr_demand",
        "community",
        "documentation",
        "originality",
        "audience",
    }
    assert only_gap["fr_demand_observed"] is False


def test_full_signals_high_confidence() -> None:
    result = score_topic(
        {
            "gap_score": 0.7,
            "fr_median_views": 20_000,
            "community_measured": True,
            "community_requests": 6,
            "community_questions": 4,
            "pages": 12,
            "theories": 2,
            "segments": [{"status": "CONFIRMED"}, {"status": "HYPOTHESIS"}],
        }
    )
    assert result["confidence"] == "HIGH"
    assert result["missing"] == []
    assert 0.6 < result["score"] <= 1


def test_english_popularity_alone_is_a_hypothesis() -> None:
    opp = build({"id": "t", "name": "Sandman"}, {"gap_score": 0.9, "pages": 0})
    assert opp["status"] == "HYPOTHESIS"
    assert opp["recommendation"] != "PRIORISER"
    assert any("NON observée" in r for r in opp["risks"])
    assert any("aucune page" in r for r in opp["risks"])


def test_formats_follow_knowledge_levels() -> None:
    assert formats_for([{"knowledge_level": "EXPERT"}])[0].startswith("EXPERTISE")
    assert len(formats_for([])) == 3
