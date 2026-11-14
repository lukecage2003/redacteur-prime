from uuid import uuid4

import pytest

from primestone.editorial import MISSION_TYPES, Corpus, Verdict, check_text, plan
from primestone.forensic import TextRow
from primestone.provenance import BoundingBox

DOC = uuid4()
BOX = BoundingBox(x=0.1, y=0.1, width=0.2, height=0.1)


def row(text: str, page: int, panel: int = 1) -> TextRow:
    return TextRow(
        id=uuid4(),
        analysis_id=uuid4(),
        document_id=DOC,
        page=page,
        order=1,
        panel_index=panel,
        kind="DIALOGUE",
        text=text,
        language="fr",
        confidence=1.0,
        speaker="Selina",
        speaker_confidence=1.0,
        bbox=BOX,
        human=True,
    )


CORPUS = Corpus(
    titles={DOC: "Nuit noire #1"},
    page_counts={DOC: 4},
    rows=[row("Je m'appelle Selina. J'ai 28 ans.", 1, 1), row("Je suis Catwoman.", 2, 2)],
    claims=[
        {
            "subject": "Selina",
            "predicate": "age",
            "value": "28",
            "evidence": [{"page": 1, "document_id": str(DOC), "excerpt": "J'ai 28 ans."}],
        }
    ],
)


def statuses(text: str) -> list[str]:
    return [c.status for c in check_text(text, CORPUS).checks]


def test_verified_quotes_pass() -> None:
    report = check_text(
        "Selina se présente : « Je suis Catwoman. » [Nuit noire #1, p. 2, case 2]. "
        "Elle dit aussi « j'ai 28 ans » [p. 1].",
        CORPUS,
    )
    assert report.verdict is Verdict.PASS
    assert [c.status for c in report.checks] == ["VERIFIED", "VERIFIED"]


def test_wrong_quote_or_panel_fails() -> None:
    assert statuses("Selina dit « Je suis Batman. » [p. 2].") == ["QUOTE_NOT_FOUND"]
    assert statuses("Selina dit « Je suis Catwoman. » [p. 2, case 1].") == ["QUOTE_NOT_FOUND"]
    assert check_text("Selina dit « Je suis Batman. » [p. 2].", CORPUS).verdict is Verdict.FAIL


def test_invalid_citations_fail() -> None:
    assert statuses("Selina dit « Je suis Catwoman. » [p. 9].") == ["INVALID_CITATION"]
    assert statuses("Selina dit « Je suis Catwoman. » [Autre titre, p. 2].") == ["INVALID_CITATION"]


def test_age_contradicting_the_work_fails_with_evidence() -> None:
    report = check_text("Selina a 35 ans au début du récit.", CORPUS)
    [check] = report.checks
    assert check.status == "CONFLICTS_WITH_EVIDENCE"
    assert "28" in check.detail
    assert check.citations[0]["page"] == 1
    assert report.verdict is Verdict.FAIL


def test_review_cases() -> None:
    assert statuses("Selina hésite longuement avant de parler [p. 2].") == ["PARAPHRASE"]
    assert statuses("Selina est la meilleure voleuse de la ville.") == ["NO_CITATION"]
    assert statuses("Elle dit « Bonsoir » [p. 3].") == ["PAGE_NOT_TRANSCRIBED"]
    assert (
        check_text("Selina est la meilleure voleuse de la ville.", CORPUS).verdict
        is Verdict.NEEDS_REVIEW
    )


def test_headings_notes_and_questions_are_not_claims() -> None:
    assert (
        statuses(
            "# Dossier : Selina\n## Points de continuité à examiner\nNote : pages non "
            "transcrites dans Nuit noire #1 : 3, 4.\nQui est-elle vraiment ?"
        )
        == ["NOT_FACTUAL"] * 4
    )


def test_plan() -> None:
    assert set(MISSION_TYPES) == {
        "CHARACTER_DOSSIER",
        "CONTINUITY_AUDIT",
        "FACT_CHECK",
        "THEORY_REVIEW",
        "RESEARCH_DOSSIER",
        "MARKET_BRIEF",
        "SOCIAL_PACKAGE",
        "SCRIPT_REVIEW",
        "PERFORMANCE_REVIEW",
    }
    assert [t.agent for t in plan("SCRIPT_REVIEW", {"script_id": "x"})][:2] == [
        "story_architect",
        "editorial_critic",
    ]
    with pytest.raises(ValueError, match="source_mission_id"):
        plan("SOCIAL_PACKAGE", {})
    assert [t.agent for t in plan("MARKET_BRIEF", {})] == ["market_analyst", "chief_editor_writer"]
    keys = [t.key for t in plan("CHARACTER_DOSSIER", {"character": "Selina"})]
    assert keys == ["prepare", "character_research", "continuity", "synthesis", "fact_check"]
    assert [t.critical for t in plan("CONTINUITY_AUDIT", {})] == [True, False, True, True, True]
    with pytest.raises(ValueError, match="character"):
        plan("CHARACTER_DOSSIER", {})
    with pytest.raises(ValueError, match="draft"):
        plan("FACT_CHECK", {"draft": "  "})
    review = plan("THEORY_REVIEW", {"theory_id": "t"})
    assert [t.agent for t in review][1] == "theory_researcher"
    with pytest.raises(ValueError, match="theory_id"):
        plan("THEORY_REVIEW", {})
    with pytest.raises(ValueError, match="question"):
        plan("RESEARCH_DOSSIER", {})
    with pytest.raises(ValueError, match="inconnu"):
        plan("X", {})


def test_quotes_with_punctuation_are_not_split() -> None:
    corpus = Corpus(
        titles={DOC: "T"},
        page_counts={DOC: 2},
        rows=[row("Selina ? Encore toi ? Tu es en retard.", 1)],
    )
    report = check_text("Bruce dit : « Selina ? Encore toi ? Tu es en retard. » [p. 1].", corpus)
    assert [c.status for c in report.checks] == ["VERIFIED"]


def test_each_quote_is_checked_against_its_own_reference() -> None:
    text = (
        "Contradiction possible : « J'ai 28 ans. » [Nuit noire #1, p. 1, case 1] "
        "et « Je suis Catwoman. » [Nuit noire #1, p. 2, case 2]."
    )
    assert statuses(text) == ["VERIFIED"]
    swapped = (
        "Contradiction : « Je suis Catwoman. » [Nuit noire #1, p. 1, case 1] "
        "et « J'ai 28 ans. » [Nuit noire #1, p. 2, case 2]."
    )
    assert statuses(swapped) == ["QUOTE_NOT_FOUND"]


def test_numbers_inside_quotes_are_not_age_claims() -> None:
    corpus = Corpus(
        titles={DOC: "T"},
        page_counts={DOC: 2},
        rows=[row("J'ai 31 ans, idiot.", 1)],
        claims=CORPUS.claims,
    )
    assert statuses_in(corpus, "Selina répond : « J'ai 31 ans, idiot. » [p. 1].") == ["VERIFIED"]


def statuses_in(corpus: Corpus, text: str) -> list[str]:
    return [c.status for c in check_text(text, corpus).checks]
