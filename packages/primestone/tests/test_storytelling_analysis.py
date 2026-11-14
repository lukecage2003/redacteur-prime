from uuid import uuid4

from primestone.editorial import Corpus, check_text
from primestone.storytelling import WEIGHTS, score, sections, work_citations

SCRIPT = """00:00 - Introduction
Et si le Sandman n'était pas le héros que vous croyez ? Neil Gaiman cache un indice en 2003.
Pourtant, personne ne le remarque.

02:10 - Le rêve
Dans The Sandman: Endless Nights (2003), Rêve affronte sa famille. Mais pourquoi cède-t-il ?
Le récit montre une famille brisée. Vous allez voir que tout tient dans une case.

05:30 - Conclusion
En résumé, le rêve se paie. Et vous, qu'en pensez-vous ?"""


def test_sections_and_timestamps() -> None:
    parts = sections(SCRIPT)
    assert [(p.title, p.start_seconds) for p in parts] == [
        ("Introduction", 0),
        ("Le rêve", 130),
        ("Conclusion", 330),
    ]
    assert sections("## A\ntexte\n## B\nautre")[1].title == "B"


def test_work_citations_library_vs_external() -> None:
    works = work_citations(SCRIPT, ["The Sandman: Endless Nights"])
    assert works == [{"title": "The Sandman: Endless Nights", "year": 2003, "status": "IN_LIBRARY"}]
    assert work_citations(SCRIPT, [])[0]["status"] == "EXTERNAL_TO_SOURCE"


def empty_corpus() -> Corpus:
    return Corpus(titles={}, page_counts={}, rows=[])


def test_score_is_bounded_and_explained() -> None:
    report = check_text(SCRIPT, empty_corpus())
    result = score(SCRIPT, report, work_citations(SCRIPT, ["The Sandman: Endless Nights"]))
    assert result["factual_veto"] is False
    assert 0 <= result["total"] <= 100
    assert set(result["criteria"]) == set(WEIGHTS)
    for key, c in result["criteria"].items():
        assert 0 <= c["score"] <= WEIGHTS[key]
        assert c["notes"]
    assert result["criteria"]["architecture"]["score"] >= 10  # 3 sections croissantes depuis 0:00
    assert result["criteria"]["accuracy"]["score"] > 0  # référence vérifiable en bibliothèque
    assert result["analysis"]["estimated_minutes"] > 0
    assert "heuristique" in result["nature"]


def test_factual_veto_zeroes_accuracy() -> None:
    doc = uuid4()
    corpus = Corpus(titles={doc: "Nuit noire #1"}, page_counts={doc: 2}, rows=[])
    bad = "00:00 - Intro\nSelina dit « Je suis Batman. » [Nuit noire #1, p. 9]."
    result = score(bad, check_text(bad, corpus), [])
    assert result["factual_veto"] is True
    assert result["criteria"]["accuracy"]["score"] == 0
    unsourced = "Une histoire sans aucune source."
    assert score(unsourced, check_text(unsourced, empty_corpus()), [])["criteria"]["accuracy"][
        "notes"
    ] == ["aucune source citée"]


def test_work_titles_from_real_script_style() -> None:
    line = (
        "Voir The Sandman: Endless Nights (2003), The Heart of a Star, puis Watchmen (1986) "
        "et selon Alan Moore, Swamp Thing (1984)."
    )
    titles = [w["title"] for w in work_citations(line, [])]
    assert titles == ["The Sandman: Endless Nights", "Watchmen", "Swamp Thing"]


def test_timestamp_ranges() -> None:
    parts = sections("0:00 - 1:35 | INTRODUCTION\ntexte\n1:35 - 4:00 | 1. QUI EST-ELLE ?\nsuite")
    assert [(p.title, p.start_seconds) for p in parts] == [
        ("INTRODUCTION", 0),
        ("1. QUI EST-ELLE ?", 95),
    ]
