"""Charte de marque Primestone : versionnée (l'évolution est conservée), vérifiable.

La charte par défaut est un POINT DE DÉPART explicitement marqué « à personnaliser » : le
propriétaire publie sa propre version (couleurs, typographies, ton, règles de miniatures,
habillage, identité sonore) ; chaque version est conservée.
"""

from __future__ import annotations

from typing import Any

from primestone.forensic import fold

DEFAULT_CHARTER: dict[str, Any] = {
    "status": "par défaut — à personnaliser par le propriétaire",
    "colors": [
        {"name": "Nuit", "hex": "#111318", "usage": "fonds"},
        {"name": "Ambre", "hex": "#D97706", "usage": "accent, mots clés"},
        {"name": "Ivoire", "hex": "#F5F1E8", "usage": "texte sur fond sombre"},
    ],
    "fonts": {"title": "sans-serif grasse condensée", "body": "sans-serif lisible"},
    "tone": {
        "do": ["précis", "curieux", "sourcé", "pédagogue sans condescendance"],
        "dont": [
            "choc",
            "incroyable",
            "hallucinant",
            "vous ne croirez jamais",
            "secret jamais révélé",
            "100 %",
            "définitivement prouvé",
        ],
    },
    "thumbnail": {
        "max_words": 4,
        "max_faces": 1,
        "require_contrast": True,
        "show_source_panel": True,
    },
    "packaging": {"title_max_chars": 60},
    "sound": {"signature": "à définir", "music": "sous licence uniquement"},
    "motion": {"lower_thirds": "palette de la charte", "transitions": "sobres"},
}


def banned_terms(charter: dict[str, Any]) -> list[str]:
    return [fold(t) for t in charter.get("tone", {}).get("dont", [])]


def check_text(text: str, charter: dict[str, Any]) -> list[str]:
    """Écarts de ton : termes bannis par la charte présents dans le texte."""
    folded = fold(text)
    return [t for t in banned_terms(charter) if t and t in folded]


def check_thumbnail(concept: dict[str, Any], charter: dict[str, Any]) -> list[str]:
    rules = charter.get("thumbnail", {})
    issues = []
    words = len(str(concept.get("text", "")).split())
    if words > int(rules.get("max_words", 4)):
        issues.append(f"{words} mots sur la miniature (charte : {rules.get('max_words')} au plus)")
    palette = {c["hex"].lower() for c in charter.get("colors", [])}
    if concept.get("colors") and not {c.lower() for c in concept["colors"]} <= palette:
        issues.append("couleurs hors charte")
    issues += [f"terme banni : {t}" for t in check_text(str(concept.get("text", "")), charter)]
    return issues
