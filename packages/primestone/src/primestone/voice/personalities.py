"""Les cinq personnalités de l'assistant vocal : ton, longueur, et ce qu'elles s'autorisent.

Aucune ne peut présenter une théorie comme un fait : les réponses factuelles passent par le
Fact Checker, quelle que soit la personnalité."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Personality:
    key: str
    name: str
    style: str
    max_sentences: int
    cites_sources: bool
    may_speculate: bool


PERSONALITIES: dict[str, Personality] = {
    p.key: p
    for p in (
        Personality(
            "conversation",
            "Conversation",
            "chaleureux, phrases courtes, tutoiement",
            3,
            False,
            False,
        ),
        Personality("research", "Research", "précis, chaque fait avec sa page", 5, True, False),
        Personality(
            "editorial",
            "Editorial",
            "angle, structure, ce qui ferait une bonne vidéo",
            4,
            True,
            False,
        ),
        Personality(
            "director", "Director", "décisions et prochaines étapes, très bref", 2, False, False
        ),
        Personality(
            "brainstorming",
            "Brainstorming",
            "idées ouvertes, toujours marquées comme hypothèses",
            5,
            False,
            True,
        ),
    )
}
