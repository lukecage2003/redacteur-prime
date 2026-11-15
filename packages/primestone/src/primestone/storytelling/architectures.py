"""Bibliothèque de techniques narratives et architectures de récit (`architectures@1`).

Uniquement des PRINCIPES transférables, rédigés pour Primestone : aucune expression, aucun
script, aucune séquence ni identité d'un autre créateur n'est reproduit. Les plans proposés
ne contiennent que des faits VÉRIFIÉS (mot pour mot) et des consignes de structure.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

METHOD = "architectures@1"


@dataclass(frozen=True)
class Technique:
    key: str
    family: str  # HOOK | RETENTION | TRANSITION | REVELATION | CONCLUSION
    principle: str
    use_when: str
    avoid: str


TECHNIQUES = (
    Technique(
        "question_ouverte",
        "HOOK",
        "Ouvrir sur une question précise dont la réponse est dans la vidéo.",
        "sujet avec un mystère ou un paradoxe",
        "les questions rhétoriques vagues ou trompeuses",
    ),
    Technique(
        "paradoxe",
        "HOOK",
        "Énoncer une contradiction apparente sourcée, puis promettre de la résoudre.",
        "deux faits vérifiés qui semblent s'opposer",
        "un paradoxe inventé ou exagéré",
    ),
    Technique(
        "in_medias_res",
        "HOOK",
        "Commencer au moment le plus fort, puis revenir au contexte.",
        "récit avec un point culminant clair",
        "révéler la conclusion entière d'emblée",
    ),
    Technique(
        "boucle_ouverte",
        "RETENTION",
        "Annoncer un élément qui sera révélé plus tard, et le payer.",
        "vidéos longues",
        "promettre sans payer (déception, perte de confiance)",
    ),
    Technique(
        "changement_de_rythme",
        "RETENTION",
        "Alterner explication, citation montrée et question.",
        "sections de plus de 2 minutes",
        "le rythme constant d'un exposé",
    ),
    Technique(
        "recapitulatif",
        "TRANSITION",
        "Résumer en une phrase avant d'ouvrir la partie suivante.",
        "entre chapitres d'une explication complexe",
        "répéter mot pour mot",
    ),
    Technique(
        "preuve_montree",
        "REVELATION",
        "Montrer la case citée au moment de l'affirmation.",
        "toute affirmation forte",
        "affirmer sans montrer la source",
    ),
    Technique(
        "contre_point",
        "REVELATION",
        "Exposer la meilleure objection avant de conclure.",
        "théories et interprétations",
        "une objection de paille",
    ),
    Technique(
        "ouverture",
        "CONCLUSION",
        "Conclure sur une question qui prolonge la réflexion du public.",
        "contenus communautaires et d'expertise",
        "un appel à l'action trompeur",
    ),
)

ARCHITECTURES: dict[str, dict[str, Any]] = {
    "ENQUETE": {
        "label": "Enquête",
        "best_for": ("EXPLORATION", "EXPERTISE"),
        "beats": (
            "Mystère (question ouverte)",
            "Indices sourcés",
            "Fausse piste réfutée",
            "Révélation (preuve montrée)",
            "Implications et contre-point",
            "Ouverture",
        ),
    },
    "CHRONOLOGIQUE": {
        "label": "Chronologie",
        "best_for": ("DISCOVERY", "EXPLORATION"),
        "beats": (
            "Point de départ",
            "Étapes clés datées",
            "Tournant",
            "Conséquences",
            "Récapitulatif",
        ),
    },
    "QUESTIONS_REPONSES": {
        "label": "Questions de la communauté",
        "best_for": ("DISCOVERY", "EXPLORATION"),
        "beats": (
            "Question la plus posée",
            "Réponse sourcée",
            "Questions suivantes",
            "Ce qui reste ouvert",
        ),
    },
    "PORTRAIT": {
        "label": "Portrait de personnage",
        "best_for": ("DISCOVERY", "EXPLORATION"),
        "beats": (
            "Qui est-il en une phrase",
            "Origine",
            "Conflit central",
            "Transformation",
            "Héritage",
        ),
    },
    "DEBAT": {
        "label": "Débat de théories",
        "best_for": ("EXPERTISE",),
        "beats": (
            "Thèse et ses preuves",
            "Antithèse et ses preuves",
            "Ce que l'œuvre tranche (canon)",
            "Ce qui reste théorie",
            "Verdict du public (ouverture)",
        ),
    },
    "COMPARATIF": {
        "label": "Comparatif",
        "best_for": ("EXPLORATION", "EXPERTISE"),
        "beats": (
            "Les deux versions",
            "Points communs sourcés",
            "Différences sourcées",
            "Ce que ça change",
        ),
    },
}


def propose(
    subject: str, facts: Sequence[str], *, level: str | None = None
) -> list[dict[str, Any]]:
    """Plusieurs architectures pour un même sujet ; les faits vérifiés sont répartis dans
    l'ordre, jamais réécrits. `level` filtre les architectures adaptées."""
    proposals = []
    for key, arch in ARCHITECTURES.items():
        if level and level not in arch["best_for"]:
            continue
        beats = list(arch["beats"])
        slots: list[dict[str, Any]] = [{"beat": b, "facts": []} for b in beats]
        for i, fact in enumerate(facts):
            slots[min(len(slots) - 1, 1 + i % max(1, len(slots) - 2))]["facts"].append(fact)
        proposals.append(
            {
                "architecture": key,
                "label": arch["label"],
                "subject": subject,
                "levels": list(arch["best_for"]),
                "outline": slots,
            }
        )
    return proposals


def techniques() -> list[dict[str, str]]:
    return [asdict(t) for t in TECHNIQUES]
