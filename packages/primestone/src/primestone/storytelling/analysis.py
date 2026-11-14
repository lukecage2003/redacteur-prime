"""Analyse et pré-notation d'un script (méthode `script-score@1`), déterministes et gratuites.

La note sur 100 suit les 8 critères du projet (Hook 15, Architecture 15, Rétention 15,
Écriture 15, Originalité 10, Oralité 10, Exactitude 15, Conclusion 5). C'est une
PRÉ-NOTATION HEURISTIQUE, explicable critère par critère, qui ne remplace pas la relecture
humaine. Le VETO FACTUEL est absolu : une erreur factuelle majeure du Fact Checker invalide le
script quel que soit son score.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Any

from primestone.editorial.factcheck import FactCheckReport, Verdict, split_sentences
from primestone.forensic import fold

METHOD = "script-score@1"
WORDS_PER_MINUTE = 150
WEIGHTS = {
    "hook": 15,
    "architecture": 15,
    "retention": 15,
    "writing": 15,
    "originality": 10,
    "orality": 10,
    "accuracy": 15,
    "conclusion": 5,
}
_TIMESTAMP = re.compile(
    r"^\s*[\[(]?(?:(\d{1,2}):)?(\d{1,2}):(\d{2})[\])]?"  # début
    r"(?:\s*[-\u2013\u2014]\s*[\[(]?(?:\d{1,2}:)?\d{1,2}:\d{2}[\])]?)?"  # fin facultative
    r"\s*(?:[-\u2013\u2014:|]\s*)?(?P<title>.*)$"
)
_HEADING = re.compile(r"^\s*#{1,3}\s+(?P<title>.+)$")
_CITATION = re.compile(r"\[[^\[\]]*p\.\s*\d+[^\[\]]*\]")
_LOOPS = (
    "mais",
    "pourtant",
    "sauf que",
    "et si",
    "pourquoi",
    "comment",
    "on y revient",
    "but",
    "yet",
    "what if",
    "why",
    "how",
)
_ANGLE = (
    "personne ne",
    "on oublie",
    "en réalité",
    "contrairement",
    "théorie",
    "hypothèse",
    "nobody",
    "actually",
    "theory",
    "overlooked",
)
_STOP_WORDS = (
    "le la les un une des de du et à a en que qui est il elle on ce se sa son ses pour pas plus "
    "dans par sur au aux ne the of and to in is it that was for on with as his her this be at "
    "by are an"
)
_STOP = set(_STOP_WORDS.split())


@dataclass(frozen=True)
class Section:
    title: str
    start_seconds: int | None
    text: str

    @property
    def words(self) -> int:
        return len(_CITATION.sub("", self.text).split())


def sections(script: str) -> list[Section]:
    """Sections horodatées (« 00:00 - Intro », « [1:02:03] … ») ou titres « ## »."""
    found: list[tuple[str, int | None, list[str]]] = []
    for line in script.splitlines():
        ts, heading = _TIMESTAMP.match(line), _HEADING.match(line)
        if ts and len(line) < 140:
            hours, minutes, secs = ts.group(1), ts.group(2), ts.group(3)
            start = int(hours or 0) * 3600 + int(minutes) * 60 + int(secs)
            found.append((ts.group("title").strip() or "Sans titre", start, []))
        elif heading:
            found.append((heading.group("title").strip(), None, []))
        elif line.strip():
            if not found:
                found.append(("Introduction", None, []))
            found[-1][2].append(line.strip())
    return [Section(t, s, "\n".join(body)) for t, s, body in found if body]


_YEAR = re.compile(r"\((?P<year>(?:19|20)\d{2})\)")
_CONNECTORS = {
    "of", "the", "and", "a", "an", "in", "on", "to", "at", "for", "de", "du", "des", "la", "le",
    "les", "et", "&", "-", "\u2013", "vs", "vs.",
}  # fmt: skip


def _title_before(prefix: str) -> str:
    """Suite maximale de mots à majuscule (ou connecteurs, numéros) juste avant « (année) »."""
    tokens = prefix.rstrip().split(" ")
    kept: list[str] = []
    for token in reversed(tokens):
        bare = token.strip(",;")
        if not bare or (token.endswith((",", ";", ".")) and kept):
            break
        if bare[0].isupper() or bare[0].isdigit() or bare[0] == "#" or bare.lower() in _CONNECTORS:
            kept.append(bare)
            continue
        break
    while kept and kept[-1].lower() in _CONNECTORS:  # pas de connecteur en tête de titre
        kept.pop()
    # « Dans The Sandman » : un mot à majuscule de début de phrase n'est pas du titre s'il est
    # suivi d'un article à majuscule.
    if len(kept) >= 2 and kept[-2] in ("The", "Le", "La", "Les", "A", "An"):
        kept.pop()
    return " ".join(reversed(kept)).strip(" :")


def work_citations(script: str, library_titles: Sequence[str]) -> list[dict[str, Any]]:
    """Références « Titre (année) » : vérifiables dans la bibliothèque, ou savoir externe à
    sourcer (jamais présenté comme vérifié)."""
    library = [fold(t) for t in library_titles]
    seen: dict[str, dict[str, Any]] = {}
    for line in script.splitlines():
        for match in _YEAR.finditer(line):
            title = _title_before(line[: match.start()])
            if len(title) < 3:
                continue
            key = f"{fold(title)}|{match.group('year')}"
            if key in seen:
                continue
            folded = fold(title)
            in_library = any(folded and (folded in t or t in folded) for t in library)
            seen[key] = {
                "title": title,
                "year": int(match.group("year")),
                "status": "IN_LIBRARY" if in_library else "EXTERNAL_TO_SOURCE",
            }
    return list(seen.values())


def _clamp(value: float, top: int) -> float:
    return round(max(0.0, min(float(top), value)), 1)


def score(script: str, report: FactCheckReport, works: Sequence[dict[str, Any]]) -> dict[str, Any]:
    parts = sections(script)
    # Script horodaté : ce qui précède le premier horodatage (titre, durée cible, ton) est le
    # brief, pas du texte dit.
    if any(p.start_seconds is not None for p in parts):
        parts = [p for p in parts if p.start_seconds is not None]
    text = _CITATION.sub("", script)
    # Les retours à la ligne d'un PDF sont visuels : les phrases se lisent sur le corps des
    # sections remis bout à bout (titres et horodatages exclus).
    spoken = " ".join(" ".join(p.text.split()) for p in parts)
    sentences = split_sentences(_CITATION.sub("", spoken))
    words = text.split()
    total_words = len(words)
    notes: dict[str, list[str]] = {k: [] for k in WEIGHTS}
    folded = fold(text)

    # Hook : ouverture courte, concrète, qui ouvre une question ou une tension.
    opening = " ".join(sentences[:3])
    opening_words = len(opening.split())
    hook = 0.0
    if sentences:
        hook += 5 if opening_words <= 60 else 2
        hook += (
            5 if ("?" in opening or any(f" {w} " in f" {fold(opening)} " for w in _LOOPS)) else 0
        )
        hook += 5 if re.search(r"\d|[A-Z][a-z]+ [A-Z]", opening) else 2
    notes["hook"].append(f"3 premières phrases : {opening_words} mots")

    # Architecture : ≥ 3 sections, horodatages croissants, équilibre des longueurs.
    arch = 0.0
    if len(parts) >= 3:
        arch += 6
    stamps = [p.start_seconds for p in parts if p.start_seconds is not None]
    if stamps and stamps == sorted(stamps) and stamps[0] == 0:
        arch += 4
    elif stamps:
        notes["architecture"].append("horodatages non croissants ou ne commençant pas à 0:00")
    lengths = [p.words for p in parts]
    if len(lengths) >= 2 and mean(lengths):
        variation = pstdev(lengths) / mean(lengths)
        arch += 5 if variation <= 0.8 else 2
        notes["architecture"].append(f"variation des longueurs de section : {variation:.2f}")
    notes["architecture"].insert(0, f"{len(parts)} section(s)")

    # Rétention : boucles ouvertes (questions, « mais », « pourtant ») réparties ; sections
    # pas trop longues (< 3 min de lecture).
    loops = sum(1 for s in sentences if "?" in s or any(f" {w} " in f" {fold(s)} " for w in _LOOPS))
    density = loops / max(1, len(sentences))
    long_sections = sum(1 for p in parts if p.words / WORDS_PER_MINUTE > 3)
    retention = 10 * min(1.0, density / 0.15) + (5 if parts and not long_sections else 2)
    notes["retention"].append(
        f"{loops} relance(s) sur {len(sentences)} phrases ; {long_sections} section(s) > 3 min"
    )

    # Écriture : longueur moyenne de phrase, répétitions, diversité lexicale.
    lengths_s = [len(s.split()) for s in sentences] or [0]
    avg = mean(lengths_s)
    content = [w for w in (fold(w) for w in words) if w and w not in _STOP and len(w) > 2]
    diversity = len(set(content)) / max(1, len(content))
    top_share = Counter(content).most_common(1)[0][1] / len(content) if content else 0
    writing = (
        (6 if 10 <= avg <= 24 else 3)
        + 5 * min(1.0, diversity / 0.5)
        + (4 if top_share < 0.04 else 1)
    )
    notes["writing"].append(
        f"{avg:.1f} mots/phrase, diversité {diversity:.2f}, mot le plus répété {top_share:.1%}"
    )

    # Originalité (heuristique faible) : angle explicite, part d'analyse.
    angle_hits = sum(folded.count(a) for a in _ANGLE)
    originality = 4 + min(6, angle_hits * 2)
    notes["originality"].append(f"{angle_hits} marqueur(s) d'angle ; heuristique faible")

    # Oralité : phrases courtes (≤ 20 mots), peu de parenthèses, adresse au public.
    short = sum(1 for n in lengths_s if n <= 20) / max(1, len(lengths_s))
    parentheses = text.count("(") - len(works)
    address = len(re.findall(r"\b(vous|tu|you)\b", text, re.IGNORECASE))
    orality = 5 * short + (3 if parentheses <= 2 else 1) + (2 if address else 0)
    notes["orality"].append(
        f"{short:.0%} de phrases courtes, {max(0, parentheses)} parenthèse(s), "
        f"{address} adresse(s) au public"
    )

    # Exactitude : Fact Checker (citations de pages) + références d'œuvres.
    counts = report.counts
    veto = report.verdict is Verdict.FAIL
    verified = counts.get("VERIFIED", 0)
    library_refs = sum(1 for w in works if w["status"] == "IN_LIBRARY")
    external = sum(1 for w in works if w["status"] == "EXTERNAL_TO_SOURCE")
    pending = counts.get("PAGE_NOT_TRANSCRIBED", 0) + counts.get("PARAPHRASE", 0)
    sourced = verified + pending + library_refs + external
    if veto:
        accuracy = 0.0
        notes["accuracy"].append("VETO : erreur factuelle majeure (Fact Checker)")
    elif not sourced:
        accuracy = 0.0
        notes["accuracy"].append("aucune source citée")
    else:
        accuracy = 15 * (verified + 0.5 * (pending + library_refs)) / sourced
        notes["accuracy"].append(
            f"{verified} citation(s) vérifiée(s), {pending + library_refs} à vérifier, "
            f"{external} référence(s) externe(s) à sourcer"
        )

    # Conclusion : dernière section identifiable, qui récapitule ou ouvre.
    last = parts[-1] if parts else None
    conclusion = 0.0
    if last and len(parts) >= 2:
        conclusion = 3 + (
            2
            if (
                "?" in last.text
                or re.search(
                    r"conclu|en résumé|finalement|abonn|in the end|subscribe",
                    fold(last.text + " " + last.title),
                )
            )
            else 0
        )
    notes["conclusion"].append(f"dernière section : {last.title if last else 'aucune'}")

    raw = {
        "hook": hook,
        "architecture": arch,
        "retention": retention,
        "writing": writing,
        "originality": originality,
        "orality": orality,
        "accuracy": accuracy,
        "conclusion": conclusion,
    }
    criteria = {
        key: {"score": _clamp(raw[key], top), "max": top, "notes": notes[key]}
        for key, top in WEIGHTS.items()
    }
    total = round(sum(_clamp(raw[key], top) for key, top in WEIGHTS.items()))
    return {
        "method": METHOD,
        "criteria": criteria,
        "total": total,
        "factual_veto": veto,
        "nature": "pré-notation heuristique : à confirmer par une relecture humaine",
        "analysis": {
            "sections": [
                {"title": p.title, "start_seconds": p.start_seconds, "words": p.words}
                for p in parts
            ],
            "words": total_words,
            "estimated_minutes": round(total_words / WORDS_PER_MINUTE, 1),
            "works": list(works),
            "fact_check": report.as_dict(),
        },
    }
