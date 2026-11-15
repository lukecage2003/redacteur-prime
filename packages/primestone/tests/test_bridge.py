from primestone.editorial import Corpus, check_text
from primestone.storytelling import ARCHITECTURES, propose, techniques
from primestone.storytelling.levels import check
from primestone.storytelling.retention import analyze, motion_intents

EMPTY = Corpus(titles={}, page_counts={}, rows=[])


def level(name: str, text: str) -> dict:
    return check(name, text, check_text(text, EMPTY), [])


def test_discovery_requires_explained_jargon_and_short_sentences() -> None:
    bad = level(
        "DISCOVERY",
        "Ce retcon change la continuité de tout le multivers sans que personne le voie.",
    )
    assert bad["ok"] is False
    assert "retcon" in bad["checks"][0]["detail"]
    good = level(
        "DISCOVERY",
        "Qui est Despair ? Un retcon, c'est-à-dire une réécriture du passé, change tout.",
    )
    assert good["checks"][0]["ok"] is True
    assert good["accuracy"].startswith("même Fact Checker")


def test_expertise_requires_counter_evidence() -> None:
    result = level("EXPERTISE", "La théorie dit que Rêve a choisi sa fin. C'est certain.")
    names = {c["check"]: c["ok"] for c in result["checks"]}
    assert names["contre-preuves discutées"] is False
    assert names["preuves vérifiées"] is False


def test_architectures_and_techniques_are_principles() -> None:
    proposals = propose("Despair", ["Fait A [T, p. 1].", "Fait B [T, p. 2]."], level="EXPERTISE")
    assert {p["architecture"] for p in proposals} == {
        k for k, a in ARCHITECTURES.items() if "EXPERTISE" in a["best_for"]
    }
    placed = [f for p in proposals[:1] for slot in p["outline"] for f in slot["facts"]]
    assert sorted(placed) == ["Fait A [T, p. 1].", "Fait B [T, p. 2]."]  # mot pour mot
    assert all(t["avoid"] for t in techniques())


def test_script_retention_and_real_drop_offs() -> None:
    script = (
        "00:00 - Intro\nEt si tout était faux ? "
        "« Je suis Catwoman. » [Nuit noire #1, p. 2, case 2].\n"
        "01:00 - Suite\nLe récit continue. " + "Le récit continue encore et encore. " * 120 + "\n"
        "05:00 - Fin\nEn réalité, elle ment."
    )
    curve = [
        {"elapsed_ratio": 0.0, "audience_watch_ratio": 1.0},
        {"elapsed_ratio": 0.5, "audience_watch_ratio": 0.9},
        {"elapsed_ratio": 0.6, "audience_watch_ratio": 0.6},
    ]
    result = analyze(script, curve)
    suite = result["sections"][1]
    assert any(f.startswith("LONGUEUR") for f in suite["flags"])
    assert any(f.startswith("TRANSITION FAIBLE") for f in suite["flags"])
    assert result["sections"][2]["revelation"] is True
    assert result["drop_offs"][0]["section"] == "Suite"
    assert result["drop_offs"][0]["evidence"] == "OBSERVED"
    intents = motion_intents(result)
    assert intents[0]["visual_moments"] == ["Montrer la case citée : Nuit noire #1, p. 2, case 2"]
    assert intents[2]["narrative_role"] == "RÉVÉLATION"
