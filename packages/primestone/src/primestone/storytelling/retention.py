"""Analyse de rétention d'un SCRIPT (`script-retention@1`) et rapprochement avec une courbe
de rétention RÉELLE si elle existe. Produit aussi les intentions transmises à Motion Studio.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from itertools import pairwise
from typing import Any

from primestone.forensic import fold
from primestone.storytelling.analysis import WORDS_PER_MINUTE, Section, sections

METHOD = "script-retention@1"
_CITATION = re.compile(
    r"\[(?P<doc>[^\[\]]+?),\s*p\.\s*(?P<page>\d+)(?:,\s*case\s*(?P<panel>\d+))?\]"
)
_REVEAL = (
    "en realite",
    "revele",
    "sauf que",
    "pourtant",
    "la verite",
    "in fact",
    "reveals",
    "twist",
)
_LINK = ("mais", "alors", "donc", "pourtant", "ensuite", "et si", "pourquoi", "comment",
         "but", "so", "then", "why", "how")  # fmt: skip


def _ngrams(text: str, n: int = 4) -> Counter[str]:
    words = [w for w in fold(text).split() if len(w) > 2]
    return Counter(" ".join(words[i : i + n]) for i in range(len(words) - n + 1))


def analyze(script: str, curve: Sequence[Mapping[str, float | None]] = ()) -> dict[str, Any]:
    parts = sections(script)
    if any(p.start_seconds is not None for p in parts):
        parts = [p for p in parts if p.start_seconds is not None]
    total_words = sum(p.words for p in parts) or 1
    repeated = {g for g, c in _ngrams(script).items() if c >= 2}
    out_sections: list[dict[str, Any]] = []
    cursor = 0
    for i, p in enumerate(parts):
        minutes = p.words / WORDS_PER_MINUTE
        start_ratio, cursor = cursor / total_words, cursor + p.words
        first = fold(p.text.split(".")[0]) if p.text else ""
        flags = []
        if minutes > 3:
            flags.append("LONGUEUR : plus de 3 min sans rupture")
        if (
            i > 0
            and not any(first.startswith(w) or f" {w} " in f" {first} " for w in _LINK)
            and "?" not in p.text[:200]
        ):
            flags.append("TRANSITION FAIBLE : ouverture sans relance ni question")
        reps = sorted(g for g in repeated if g in fold(p.text))
        if reps:
            flags.append(f"RÉPÉTITION : {reps[0]}")
        reveals = [m for m in _REVEAL if m in fold(p.text)]
        citations = [m.groupdict() for m in _CITATION.finditer(p.text)]
        visual = [
            f"Montrer la case citée : {c['doc']}, p. {c['page']}"
            + (f", case {c['panel']}" if c["panel"] else "")
            for c in citations
        ]
        if not visual and minutes > 1.5:
            visual.append(
                "Illustrer (case, chronologie ou carte) : long passage sans élément visuel"
            )
        out_sections.append(
            {
                "title": p.title,
                "start_seconds": p.start_seconds,
                "start_ratio": round(start_ratio, 3),
                "minutes": round(minutes, 1),
                "flags": flags,
                "revelation": bool(reveals),
                "visual_moments": visual,
            }
        )
    drops = []
    points = [p for p in curve if p.get("audience_watch_ratio") is not None]
    for a, b in pairwise(points):
        delta = float(b["audience_watch_ratio"] or 0) - float(a["audience_watch_ratio"] or 0)
        if delta <= -0.05:
            ratio = float(b["elapsed_ratio"] or 0)
            section = next(
                (s["title"] for s in reversed(out_sections) if float(s["start_ratio"]) <= ratio),
                None,
            )
            drops.append(
                {
                    "at_ratio": ratio,
                    "drop": round(delta, 3),
                    "section": section,
                    "evidence": "OBSERVED",
                }
            )
    return {
        "method": METHOD,
        "sections": out_sections,
        "drop_offs": drops,
        "note": "Repères du script = HYPOTHÈSES ; décrochages = OBSERVÉS sur la courbe réelle.",
    }


def motion_intents(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    """Intentions de montage transmises à Motion Studio (contrat 1.1)."""
    return [
        {
            "section": s["title"],
            "start_seconds": s["start_seconds"],
            "narrative_role": "RÉVÉLATION" if s["revelation"] else "EXPOSITION",
            "visual_moments": s["visual_moments"],
            "pacing": "rompre le rythme"
            if any(f.startswith("LONGUEUR") for f in s["flags"])
            else "normal",
        }
        for s in analysis["sections"]
    ]


__all__ = ["METHOD", "Section", "analyze", "motion_intents"]
