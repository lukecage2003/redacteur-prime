"""Packaging Laboratory (méthode `packaging@1`) : titres, miniatures, promesses, accroches.

Tout est dérivé des faits VÉRIFIÉS du script et du sujet ; chaque proposition est contrôlée :
- honnêteté : les noms du titre figurent dans le script ; aucun terme banni (charte) ; une
  théorie n'est jamais présentée comme un fait ;
- lisibilité : longueur, nombre de mots, majuscules ;
- adéquation au niveau : pas de jargon pour un public débutant.
Aucune prédiction de CTR ni de vues : les meilleures candidates deviennent des EXPÉRIENCES.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from primestone.creative.brand import check_text, check_thumbnail
from primestone.forensic import fold
from primestone.storytelling.levels import JARGON

METHOD = "packaging@1"
_QUOTE = re.compile(r"«\s*(.+?)\s*»")
_CITATION = re.compile(r"\[[^\[\]]*p\.\s*\d+[^\[\]]*\]")
_NAME = re.compile(r"\b[A-Z][a-zà-ÿ]+(?:\s+[A-Z][a-zà-ÿ]+)*\b")


def _clean(fact: str) -> str:
    return " ".join(_CITATION.sub("", fact).split()).rstrip(" .")


def _titles(subject: str, quotes: Sequence[str], theory: bool) -> list[str]:
    q = quotes[0] if quotes else None
    candidates = [
        f"Pourquoi {subject} ?",
        f"{subject} expliqué",
        f"{subject} : ce que les pages montrent vraiment",
        f"Ce que {subject} change à tout",
        f"{subject}, l'histoire complète",
        f"{subject} : la question que personne ne pose",
        f"Comprendre {subject} en une vidéo",
        f"{subject} : les preuves",
        f"« {q} » : ce que cette phrase révèle" if q else f"{subject} : le détail qui compte",
        f"{subject} : une théorie à l'épreuve" if theory else f"{subject} : erreurs fréquentes",
    ]
    return list(dict.fromkeys(candidates))[:10]


def _check_title(
    title: str, script: str, charter: dict[str, Any], level: str | None
) -> dict[str, Any]:
    folded_script = fold(script)
    issues = []
    for name in _NAME.findall(title):
        if fold(name) not in folded_script and fold(name) not in (
            "pourquoi",
            "comprendre",
            "ce",
            "les",
        ):
            issues.append(f"« {name} » absent du script (promesse non tenue)")
    issues += [f"terme banni : {t}" for t in check_text(title, charter)]
    if "theorie" in fold(title) and "theorie" not in folded_script:
        issues.append("annonce une théorie que le script n'aborde pas")
    max_chars = int(charter.get("packaging", {}).get("title_max_chars", 60))
    readability = []
    if len(title) > max_chars:
        readability.append(f"{len(title)} caractères (> {max_chars}, risque de troncature)")
    letters = [c for c in title if c.isalpha()]
    if letters and sum(c.isupper() for c in letters) / len(letters) > 0.5:
        readability.append("trop de majuscules")
    fit = []
    if level == "DISCOVERY":
        jargon = [j for j in JARGON if re.search(rf"\b{re.escape(j)}\b", fold(title))]
        if jargon:
            fit.append(f"jargon pour un public débutant : {', '.join(jargon)}")
    return {
        "title": title,
        "honest": not issues,
        "issues": issues,
        "readability": readability or ["lisible"],
        "audience_fit": fit or ["adapté"],
        "chars": len(title),
    }


def build(
    *,
    subject: str,
    script: str,
    verified_facts: Sequence[str],
    charter: dict[str, Any],
    level: str | None = None,
    extra_titles: Sequence[str] = (),
) -> dict[str, Any]:
    quotes = [q for f in verified_facts for q in _QUOTE.findall(f)]
    theory = "theorie" in fold(script)
    titles = [
        _check_title(t, script, charter, level)
        for t in [*_titles(subject, quotes, theory), *extra_titles]
    ]
    palette = [c["hex"] for c in charter.get("colors", [])][:2]
    concepts = [
        {
            "concept": "Case citée en gros plan",
            "composition": "la case source occupe 60 % ; légende sobre",
            "text": subject.split()[0] if subject else "",
            "colors": palette,
            "emotion": "curiosité",
        },
        {
            "concept": "Visage expressif du personnage",
            "composition": "un visage, regard vers le texte",
            "text": f"{subject.split()[0]} ?" if subject else "?",
            "colors": palette,
            "emotion": "intrigue",
        },
        {
            "concept": "Contraste avant / après",
            "composition": "deux moitiés, séparation nette",
            "text": "Avant / après",
            "colors": palette,
            "emotion": "transformation",
        },
        {
            "concept": "Objet symbole isolé",
            "composition": "objet centré sur fond uni de la charte",
            "text": "",
            "colors": palette,
            "emotion": "mystère",
        },
        {
            "concept": "Citation forte",
            "composition": "trois mots de la citation vérifiée, gros caractères",
            "text": " ".join(quotes[0].split()[:3]) if quotes else subject,
            "colors": palette,
            "emotion": "tension",
        },
    ]
    for c in concepts:
        c["brand_issues"] = check_thumbnail(c, charter)
    clean = [_clean(f) for f in verified_facts]
    promises = [f"Comprendre {subject}, preuves à l'appui."]
    promises += [f"Découvrir pourquoi : {c}" for c in clean[:2]]
    # Promesses de méthode (jamais des affirmations) pour compléter jusqu'à trois.
    promises += [
        "Distinguer ce que l'œuvre établit de ce qui reste à prouver.",
        "Repartir avec les références exactes pour vérifier par soi-même.",
    ]
    hooks = [f for f in verified_facts[:3]] or [f"Pourquoi {subject} ?"]
    honest = [t for t in titles if t["honest"] and t["readability"] == ["lisible"]]
    tests = []
    if len(honest) >= 2:
        tests.append(
            {
                "variable": "TITLE",
                "hypothesis": f"« {honest[0]['title']} » obtient un meilleur CTR que "
                + f"« {honest[1]['title']} »",
                "variants": [honest[0]["title"], honest[1]["title"]],
                "metric": "ctr",
                "how": "YouTube « Tester et comparer », puis primestone-performance experiment-*",
            }
        )
    tests.append(
        {
            "variable": "THUMBNAIL",
            "hypothesis": "La case citée en gros plan fait mieux que le visage expressif",
            "variants": [concepts[0]["concept"], concepts[1]["concept"]],
            "metric": "ctr",
            "how": "YouTube « Tester et comparer »",
        }
    )
    return {
        "method": METHOD,
        "subject": subject,
        "titles": titles,
        "thumbnails": concepts,
        "promises": promises[:3],
        "hooks": hooks[:3],
        "coherence": {
            "promise_supported": bool(verified_facts),
            "note": "chaque promesse repose sur un fait vérifié du script"
            if verified_facts
            else "aucun fait vérifié : promesses à étayer avant publication",
        },
        "tests": tests,
        "rule": "Aucune prédiction de CTR ou de vues : seules les expériences tranchent.",
    }
