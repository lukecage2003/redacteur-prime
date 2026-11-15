from primestone.creative import DEFAULT_CHARTER, build, check_thumbnail

SCRIPT = "00:00 - Intro\nDespair parle à Superman. « Je suis l'espoir. » [Kingdom, p. 2]."
FACTS = ["Despair parle : « Je suis l'espoir. » [Kingdom, p. 2]."]


def test_ten_titles_five_thumbnails_three_promises_three_hooks() -> None:
    p = build(subject="Despair", script=SCRIPT, verified_facts=FACTS, charter=DEFAULT_CHARTER)
    assert len(p["titles"]) == 10
    assert len(p["thumbnails"]) == 5
    assert len(p["promises"]) == 3
    assert 1 <= len(p["hooks"]) <= 3
    assert all("ctr" not in str(t).lower() or "prédiction" in p["rule"] for t in p["titles"])
    assert p["tests"][0]["variable"] == "TITLE"


def test_dishonest_titles_are_refused() -> None:
    p = build(
        subject="Despair",
        script=SCRIPT,
        verified_facts=FACTS,
        charter=DEFAULT_CHARTER,
        extra_titles=["Batman révèle un secret CHOC", "Despair : incroyable !"],
    )
    refused = {t["title"]: t["issues"] for t in p["titles"] if not t["honest"]}
    assert any("Batman" in i for i in refused["Batman révèle un secret CHOC"])
    assert any("banni" in i for i in refused["Despair : incroyable !"])


def test_discovery_titles_avoid_jargon_and_long_titles_flagged() -> None:
    p = build(
        subject="Despair",
        script=SCRIPT + " retcon",
        verified_facts=FACTS,
        charter=DEFAULT_CHARTER,
        level="DISCOVERY",
        extra_titles=["Despair et le retcon " + "x" * 60],
    )
    last = p["titles"][-1]
    assert "jargon" in last["audience_fit"][0]
    assert "troncature" in last["readability"][0]


def test_thumbnail_brand_rules() -> None:
    issues = check_thumbnail(
        {"text": "un deux trois quatre cinq", "colors": ["#FF00FF"]}, DEFAULT_CHARTER
    )
    assert any("mots" in i for i in issues)
    assert "couleurs hors charte" in issues
