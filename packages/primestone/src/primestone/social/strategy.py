"""Content Strategist : déclinaisons par plateforme, déterministes et gratuites.

Entrée : un livrable APPROUVÉ et son rapport du Fact Checker. Seules les phrases VERIFIED sont
reprises, telles quelles, avec leur référence : aucune reformulation ne peut introduire d'erreur.
Chaque fait reçoit un rôle narratif (tension, affirmation, fait) et sa section d'origine ;
chaque plateforme reçoit une structure propre (chapitres, accroche → développement → question,
cartes) et, autant que possible, une sélection différente : pas de découpage mécanique.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from primestone.social.platforms import PLATFORMS

METHOD = "social-package@1"
WORDS_PER_SECOND = 2.5  # ~150 mots/minute : estimation de durée de lecture à voix haute
_CITATION = re.compile(r"\[[^\[\]]*p\.\s*\d+[^\[\]]*\]")
_TENSION = ("contradiction", "contre-preuve", "élément contre", "contredit")
_CLAIM = ("affirme", "se présente", "se présente comme")
MAX_CAROUSEL_FACTS = 18  # 20 cartes au plus : couverture + 18 faits + sources


@dataclass(frozen=True)
class Beat:
    text: str
    role: str  # TENSION | CLAIM | FACT
    section: str
    citations: tuple[str, ...]

    @property
    def words(self) -> int:
        return len(_CITATION.sub("", self.text).split())


def _role(sentence: str) -> str:
    lowered = sentence.lower()
    if any(k in lowered for k in _TENSION):
        return "TENSION"
    if any(k in lowered for k in _CLAIM):
        return "CLAIM"
    return "FACT"


def beats(deliverable: str, checks: Sequence[dict[str, Any]]) -> list[Beat]:
    """Faits vérifiés, dans l'ordre du livrable, avec leur section et leur rôle."""
    sections: list[tuple[int, str]] = [(0, "Introduction")]
    for match in re.finditer(r"^#{2}\s+(.+)$", deliverable, re.MULTILINE):
        sections.append((match.start(), match.group(1).strip()))
    found: list[Beat] = []
    seen: set[str] = set()
    for check in checks:
        sentence = check["sentence"]
        if check["status"] != "VERIFIED" or sentence in seen:
            continue
        seen.add(sentence)
        position = deliverable.find(sentence)
        section = next(
            (name for start, name in reversed(sections) if start <= max(position, 0)),
            "Introduction",
        )
        found.append(Beat(sentence, _role(sentence), section, tuple(_CITATION.findall(sentence))))
    return found


def _seconds(items: Sequence[Beat]) -> int:
    return round(sum(b.words for b in items) / WORDS_PER_SECOND)


def _pick_short(pool: Sequence[Beat], avoid: set[str]) -> list[Beat]:
    """Accroche (tension > affirmation > fait), puis jusqu'à 2 développements d'autres
    sections si possible, en évitant les faits déjà pris par une autre plateforme."""
    fresh = [b for b in pool if b.text not in avoid] or list(pool)
    order = {"TENSION": 0, "CLAIM": 1, "FACT": 2}
    hook = min(fresh, key=lambda b: (order[b.role], fresh.index(b)))
    body: list[Beat] = []
    for candidate in sorted(fresh, key=lambda b: (b.section == hook.section, fresh.index(b))):
        if candidate is hook or candidate in body:
            continue
        body.append(candidate)
        if len(body) == 2:
            break
    return [hook, *body]


def build_package(
    *,
    source_title: str,
    deliverable: str,
    checks: Sequence[dict[str, Any]],
    platforms: Sequence[str] = tuple(PLATFORMS),
    market_angle: str | None = None,
) -> dict[str, Any]:
    unknown = [p for p in platforms if p not in PLATFORMS]
    if unknown:
        raise ValueError(f"plateforme inconnue : {', '.join(unknown)}")
    pool = beats(deliverable, checks)
    if not pool:
        raise ValueError("aucun fait vérifié dans le livrable source : rien à décliner")
    excluded = sorted(
        {c["sentence"] for c in checks if c["status"] not in ("VERIFIED", "NOT_FACTUAL")}
    )
    package: dict[str, Any] = {
        "method": METHOD,
        "source_title": source_title,
        "facts_available": len(pool),
        "excluded_unverified": excluded,
        "market_angle": market_angle,
        "platforms": {},
    }
    used: set[str] = set()
    for key in platforms:
        spec = PLATFORMS[key]
        if key == "youtube_long":
            chapters: dict[str, list[Beat]] = {}
            for b in pool:
                chapters.setdefault(b.section, []).append(b)
            content: dict[str, Any] = {
                "chapters": [
                    {"title": name, "facts": [b.text for b in items]}
                    for name, items in chapters.items()
                ],
                "sources": sorted({c for b in pool for c in b.citations}),
                "warnings": []
                if len(chapters) >= 3
                else ["moins de 3 chapitres : YouTube n'affichera pas de chapitres"],
            }
        elif key == "instagram_carousel":
            facts = pool[:MAX_CAROUSEL_FACTS]
            content = {
                "cover": source_title,
                "cards": [b.text for b in facts],
                "sources": sorted({c for b in facts for c in b.citations}),
                "slides": len(facts) + 2,
                "warnings": []
                if len(pool) <= MAX_CAROUSEL_FACTS
                else [f"{len(pool) - MAX_CAROUSEL_FACTS} fait(s) laissé(s) de côté (20 cartes)"],
            }
        else:
            picked = _pick_short(pool, used)
            used.update(b.text for b in picked)
            content = {
                "hook": picked[0].text,
                "hook_role": picked[0].role,
                "body": [b.text for b in picked[1:]],
                "context": f"source : {source_title}",
                "closing_question": "Et vous, vous l'aviez remarqué ?",
                "estimated_seconds": _seconds(picked),
                "estimate": "lecture à voix haute à ~150 mots/minute (ESTIMATE)",
            }
        package["platforms"][key] = {"spec": spec.as_dict(), "content": content}
    return package


def render(package: dict[str, Any]) -> str:
    """Texte vérifiable : chaque fait garde sa citation ; le reste est en « Note : » ou titre."""
    title = package["source_title"]
    lines = [
        f"# Déclinaisons sociales : {title}",
        "Note : seuls les faits vérifiés du livrable approuvé sont repris, mot pour mot.",
    ]
    if package["market_angle"]:
        lines.append(f"Note : angle marché (ESTIMATE) : {package['market_angle']}")
    for key, block in package["platforms"].items():
        spec, content = block["spec"], block["content"]
        lines.append(f"## {spec['name']} — {spec['aspect']}")
        lines.append(
            f"Note : rôle : {spec['role']} ; cible : {spec['editorial_target']} ; formats vérifiés "
            f"le {spec['checked_on']}, à revérifier."
        )
        if key == "youtube_long":
            for n, chapter in enumerate(content["chapters"], start=1):
                lines.append(f"### Chapitre {n} — {chapter['title']}")
                lines.extend(chapter["facts"])
            lines.append("### Description : sources")
            lines.extend(f"Note : {source}" for source in content["sources"])
        elif key == "instagram_carousel":
            lines.append(f"### Carte 1 — couverture : {content['cover']}")
            for n, card in enumerate(content["cards"], start=2):
                lines.append(f"### Carte {n}")
                lines.append(card)
            lines.append(f"### Carte {content['slides']} — sources")
            lines.extend(f"Note : {source}" for source in content["sources"])
        else:
            lines.append("### Accroche (3 premières secondes)")
            lines.append(content["hook"])
            lines.append("### Développement")
            lines.extend(content["body"])
            lines.append(f"Note : contexte à l'écran : {content['context']}.")
            lines.append(f"### Question finale\n{content['closing_question']}")
            lines.append(
                f"Note : durée estimée {content['estimated_seconds']} s ({content['estimate']})."
            )
        lines.extend(f"Note : attention : {w}." for w in content.get("warnings", []))
    if package["excluded_unverified"]:
        lines.append("## Écarté (non vérifié dans le livrable source)")
        lines.append(f"Note : {len(package['excluded_unverified'])} phrase(s) non reprise(s).")
    return "\n".join(lines)
