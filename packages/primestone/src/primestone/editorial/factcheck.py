"""Vérificateur de faits (Fact Checker) — déterministe, gratuit.

Format de citation attendu dans un texte :

    Selina affirme : « Je suis Catwoman. » [Nuit noire #1, p. 2, case 2]
    « Encore toi ? » [p. 1]                      (titre facultatif s'il n'y a qu'un document)

Pour chaque phrase :
- VERIFIED            toutes les citations « … » figurent dans la transcription servie de la page
                      (et de la case, si elle est précisée) ;
- QUOTE_NOT_FOUND     une citation n'y figure pas (erreur majeure) ;
- INVALID_CITATION    document ou page inexistants (erreur majeure) ;
- CONFLICTS_WITH_EVIDENCE  un âge attribué à un personnage contredit ses affirmations
                      relevées dans l'œuvre (erreur majeure, preuves jointes) ;
- PAGE_NOT_TRANSCRIBED  page citée non transcrite : invérifiable ;
- PARAPHRASE          référence sans citation exacte : à relire par un humain ;
- NO_CITATION         phrase factuelle sans référence ;
- NOT_FACTUAL         titre (« # »), ligne éditoriale (« Note : »), question (ignorée).
Verdict global : FAIL si une erreur majeure, NEEDS_REVIEW si un point invérifiable,
PASS sinon. Un texte FAIL n'est jamais validé, quelle que soit sa qualité.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID

from primestone.forensic import TextRow, fold

MAJOR = {"QUOTE_NOT_FOUND", "INVALID_CITATION", "CONFLICTS_WITH_EVIDENCE"}
REVIEW = {"PAGE_NOT_TRANSCRIBED", "PARAPHRASE", "NO_CITATION"}

_CITATION = re.compile(
    r"\[(?:(?P<doc>[^\[\]]+?),\s*)?p\.\s*(?P<page>\d+)(?:,\s*case\s*(?P<panel>\d+))?\]",
    re.IGNORECASE,
)
_QUOTE = re.compile(r"«\s*(.+?)\s*»|“(.+?)”|\"(.+?)\"")
_AGE = re.compile(r"(\d{1,3})\s*ans\b|(\d{1,3})\s*years?\s*old\b", re.IGNORECASE)
_PLACEHOLDER = re.compile("\x00(\\d+)\x00")
_SENTENCE = re.compile(r"(?<=[.!?…\]])\s+(?=[A-ZÀ-Ý\x00#\-•*])")


class Verdict(StrEnum):
    PASS = "PASS"  # noqa: S105 - verdict, pas un mot de passe
    NEEDS_REVIEW = "NEEDS_REVIEW"
    FAIL = "FAIL"


@dataclass(frozen=True)
class SentenceCheck:
    sentence: str
    status: str
    detail: str
    citations: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class FactCheckReport:
    verdict: Verdict
    checks: tuple[SentenceCheck, ...]
    counts: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "counts": self.counts,
            "checks": [
                {
                    "sentence": c.sentence,
                    "status": c.status,
                    "detail": c.detail,
                    "citations": list(c.citations),
                }
                for c in self.checks
            ],
        }


@dataclass(frozen=True)
class Corpus:
    """Ce que le vérificateur sait de l'œuvre : documents, transcriptions servies, affirmations."""

    titles: dict[UUID, str]
    page_counts: dict[UUID, int]
    rows: Sequence[TextRow]
    claims: Sequence[dict[str, Any]] = ()

    def resolve(self, label: str | None) -> UUID | None:
        if label is None:
            return next(iter(self.titles)) if len(self.titles) == 1 else None
        wanted = fold(label)
        for doc_id, title in self.titles.items():
            if fold(title) == wanted:
                return doc_id
        return None


def _mask_quotes(line: str) -> tuple[str, list[str]]:
    quotes: list[str] = []

    def protect(match: re.Match[str]) -> str:
        quotes.append(match.group(0))
        return f"\x00{len(quotes) - 1}\x00"

    return _QUOTE.sub(protect, line), quotes


def split_sentences(text: str) -> list[str]:
    """Découpe en phrases sans jamais couper à l'intérieur d'une citation « … »."""
    parts: list[str] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        masked, quotes = _mask_quotes(line.strip())
        for piece in _SENTENCE.split(masked):
            restored = _PLACEHOLDER.sub(lambda m, q=quotes: q[int(m.group(1))], piece).strip()
            if restored:
                parts.append(restored)
    return parts


def _is_factual(sentence: str) -> bool:
    """Titres (« # ») et lignes éditoriales (« Note : ») ne sont pas des affirmations."""
    if sentence.startswith("#") or fold(sentence).startswith("note "):
        return False
    bare = sentence.lstrip("*-• ").strip()
    if not bare or bare.endswith("?") or bare.endswith(":"):
        return False
    return len(bare.split()) >= 4 or bool(_CITATION.search(bare))


def check_text(text: str, corpus: Corpus) -> FactCheckReport:
    pages: dict[tuple[UUID, int], list[TextRow]] = defaultdict(list)
    for row in corpus.rows:
        pages[(row.document_id, row.page)].append(row)
    ages: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for claim in corpus.claims:
        if claim.get("predicate") == "age" and claim.get("subject"):
            ages[fold(claim["subject"])].append(claim)

    checks: list[SentenceCheck] = []
    for sentence in split_sentences(text):
        citations = list(_CITATION.finditer(sentence))
        # Les nombres À L'INTÉRIEUR des citations sont vérifiés comme citations, pas comme âges.
        conflict = _age_conflict(_QUOTE.sub(" ", sentence), ages)
        if conflict:
            checks.append(
                SentenceCheck(sentence, "CONFLICTS_WITH_EVIDENCE", conflict[0], conflict[1])
            )
            continue
        if not citations:
            status = "NO_CITATION" if _is_factual(sentence) else "NOT_FACTUAL"
            detail = "affirmation sans référence" if status == "NO_CITATION" else ""
            checks.append(SentenceCheck(sentence, status, detail))
            continue

        refs: list[dict[str, Any]] = []
        status, detail = "VERIFIED", "citations retrouvées dans les pages citées"
        previous_end = 0
        for match in citations:
            # Les citations « … » appartiennent à la référence qui les suit immédiatement.
            own_quotes = [
                next(g for g in q.groups() if g)
                for q in _QUOTE.finditer(sentence[previous_end : match.start()])
            ]
            previous_end = match.end()
            doc_id = corpus.resolve(match.group("doc"))
            page = int(match.group("page"))
            panel = int(match.group("panel")) if match.group("panel") else None
            ref = {"document": match.group("doc"), "page": page, "panel": panel}
            refs.append(ref)
            if doc_id is None or not 1 <= page <= corpus.page_counts.get(doc_id, 0):
                status, detail = "INVALID_CITATION", f"référence introuvable : {match.group(0)}"
                break
            ref["document_id"] = str(doc_id)
            if not pages.get((doc_id, page)):
                if status == "VERIFIED":
                    status, detail = (
                        "PAGE_NOT_TRANSCRIBED",
                        f"page {page} non transcrite : invérifiable",
                    )
                continue
            if not own_quotes:
                if status == "VERIFIED":
                    status, detail = (
                        "PARAPHRASE",
                        "référence sans citation exacte : relecture humaine",
                    )
                continue
            texts = [r for r in pages[(doc_id, page)] if panel is None or r.panel_index == panel]
            haystack = " ".join(fold(r.text) for r in texts)
            missing = [q for q in own_quotes if fold(q) not in haystack]
            if missing:
                where = f"p. {page}" + (f", case {panel}" if panel else "")
                status, detail = "QUOTE_NOT_FOUND", f"« {missing[0]} » absent de {where}"
                break
        checks.append(SentenceCheck(sentence, status, detail, tuple(refs)))

    counts: dict[str, int] = defaultdict(int)
    for c in checks:
        counts[c.status] += 1
    if any(c.status in MAJOR for c in checks):
        verdict = Verdict.FAIL
    elif any(c.status in REVIEW for c in checks):
        verdict = Verdict.NEEDS_REVIEW
    else:
        verdict = Verdict.PASS
    return FactCheckReport(verdict, tuple(checks), dict(counts))


def _age_conflict(
    sentence: str, ages: dict[str, list[dict[str, Any]]]
) -> tuple[str, tuple[dict[str, Any], ...]] | None:
    stated = [int(a or b) for a, b in _AGE.findall(sentence)]
    if not stated:
        return None
    folded = f" {fold(sentence)} "
    for name, claims in ages.items():
        if f" {name} " not in folded:
            continue
        values = {int(c["value"]) for c in claims if str(c.get("value", "")).isdigit()}
        wrong = [v for v in stated if values and v not in values]
        if wrong:
            evidence = tuple(
                {"page": e["page"], "document_id": e["document_id"], "excerpt": e["excerpt"]}
                for c in claims
                for e in c.get("evidence", [])
            )
            shown = ", ".join(str(v) for v in sorted(values))
            return (
                f"âge {wrong[0]} non attesté pour ce personnage (affirmé dans l'œuvre : {shown})",
                evidence,
            )
    return None
