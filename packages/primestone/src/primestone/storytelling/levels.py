"""Audience Bridge : un même sujet à trois niveaux (méthode `levels@1`).

- DISCOVERY : accessible, vocabulaire simple, contexte minimal, intérêt immédiat ;
- EXPLORATION : contexte documentaire, références, explications, connexions ;
- EXPERTISE : continuité, cosmologie, interprétations, preuves ET contre-preuves.

L'exactitude ne se négocie à aucun niveau : le même Fact Checker et le même veto s'appliquent
partout. Ces contrôles ne mesurent que l'adéquation au niveau.
"""

from __future__ import annotations

import re
from statistics import mean
from typing import Any

from primestone.editorial.factcheck import FactCheckReport, split_sentences
from primestone.forensic import fold

METHOD = "levels@1"
LEVELS = ("DISCOVERY", "EXPLORATION", "EXPERTISE")
# Termes de spécialiste qui exigent une explication pour un public débutant.
JARGON = (
    "retcon", "crossover", "continuite", "cosmologie", "multivers", "earth-616", "terre-616",
    "run", "arc", "event", "reboot", "canon", "elseworld", "one-shot", "tie-in", "omniverse",
)  # fmt: skip
EXPLAIN_MARKERS = ("c'est-a-dire", "autrement dit", "c'est ", "qui est", "ce qu'on appelle",
                   "signifie", "that is", "which means", "means", "called")  # fmt: skip
COUNTER_MARKERS = ("pourtant", "cependant", "au contraire", "contre-preuve", "a l'inverse",
                   "objection", "however", "on the other hand", "counter")  # fmt: skip
_CITATION = re.compile(r"\[[^\[\]]*p\.\s*\d+[^\[\]]*\]")


def check(
    level: str, script: str, report: FactCheckReport, works: list[dict[str, Any]]
) -> dict[str, Any]:
    if level not in LEVELS:
        raise ValueError(f"niveau inconnu : {level}")
    text = _CITATION.sub("", script)
    folded = fold(text)
    sentences = split_sentences(" ".join(text.split()))
    words = len(text.split())
    jargon = sorted({j for j in JARGON if re.search(rf"\b{re.escape(j)}\b", folded)})
    explained = [
        j
        for j in jargon
        if any(
            m in folded[max(0, folded.find(j) - 80) : folded.find(j) + 120] for m in EXPLAIN_MARKERS
        )
    ]
    page_citations = len(_CITATION.findall(script))
    verified = report.counts.get("VERIFIED", 0)
    counter = any(m in folded for m in COUNTER_MARKERS)
    avg_sentence = mean(len(s.split()) for s in sentences) if sentences else 0.0
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "ok": ok, "detail": detail})

    if level == "DISCOVERY":
        add(
            "jargon expliqué",
            set(jargon) <= set(explained),
            f"termes non expliqués : {', '.join(sorted(set(jargon) - set(explained))) or 'aucun'}",
        )
        add("phrases courtes", avg_sentence <= 18, f"{avg_sentence:.1f} mots par phrase (≤ 18)")
        add("format court", words <= 1500, f"{words} mots (≤ 1 500, environ 10 min)")
        add(
            "accroche immédiate",
            bool(sentences) and ("?" in sentences[0] or len(sentences[0].split()) <= 20),
            "la première phrase pose une question ou tient en 20 mots",
        )
    elif level == "EXPLORATION":
        refs = page_citations + len(works)
        add("références", refs >= 2, f"{refs} référence(s) (≥ 2 : pages ou œuvres)")
        add(
            "jargon expliqué",
            len(explained) >= len(jargon) / 2,
            f"{len(explained)}/{len(jargon)} terme(s) de spécialiste expliqué(s)",
        )
    else:
        add("preuves vérifiées", verified >= 3, f"{verified} citation(s) vérifiée(s) (≥ 3)")
        add("contre-preuves discutées", counter, "objection ou contre-preuve explicitement traitée")
        add(
            "théories annoncées",
            "theorie" not in folded
            or any(
                m in folded
                for m in ("hypothese", "theorie :", "selon cette theorie", "il est possible")
            ),
            "toute théorie est présentée comme telle",
        )
    return {
        "method": METHOD,
        "level": level,
        "ok": all(c["ok"] for c in checks),
        "checks": checks,
        "accuracy": "même Fact Checker et même veto qu'aux autres niveaux",
    }
