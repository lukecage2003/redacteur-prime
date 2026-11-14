"""Calcul transparent du niveau, du statut et de la confiance d'une théorie.

Règles (méthode `lab-confidence@1`, documentée dans ADR-0014) :

- poids d'une preuve active : CANON vérifiée sur la transcription 1.0 ; CANON visuelle
  (sans extrait, attestée par un humain) 0.8 ; CANON non vérifiable (page non transcrite) 0.6 ;
  INTERPRETATION 0.4 ; SPECULATION 0.1 ;
- confiance = soutien / (soutien + contre + 1) — le « + 1 » est un scepticisme de principe :
  une seule preuve ne dépasse jamais 0.5 ; tant que la recherche de contre-preuves n'a pas été
  faite, la confiance est plafonnée à 0.5 ;
- niveau THEORY seulement avec au moins une preuve CANON solide (vérifiée ou visuelle) ET une
  recherche de contre-preuves effectuée ; sinon SPECULATION. Jamais CANON ;
- statut : OPEN (aucune preuve), SUPPORTED (soutien sans contre-preuve), CONTESTED (les deux,
  ou contre-preuves faibles seulement), REFUTED (contre > soutien avec une contre-preuve solide).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

METHOD = "lab-confidence@1"
UNSEARCHED_CAP = 0.5


@dataclass(frozen=True)
class EvidenceInput:
    role: str  # SUPPORTS | REFUTES
    level: str  # CANON | INTERPRETATION | SPECULATION
    verified: bool
    has_excerpt: bool


@dataclass(frozen=True)
class Score:
    level: str
    status: str
    confidence: float
    support: float
    against: float
    explanation: tuple[str, ...]


def weight(e: EvidenceInput) -> float:
    if e.level == "CANON":
        if e.verified:
            return 1.0
        return 0.6 if e.has_excerpt else 0.8
    return 0.4 if e.level == "INTERPRETATION" else 0.1


def is_solid(e: EvidenceInput) -> bool:
    return e.level == "CANON" and (e.verified or not e.has_excerpt)


def score(evidence: Sequence[EvidenceInput], *, counter_search_done: bool) -> Score:
    support = round(sum(weight(e) for e in evidence if e.role == "SUPPORTS"), 3)
    against = round(sum(weight(e) for e in evidence if e.role == "REFUTES"), 3)
    solid_support = sum(1 for e in evidence if e.role == "SUPPORTS" and is_solid(e))
    solid_against = sum(1 for e in evidence if e.role == "REFUTES" and is_solid(e))
    raw = support / (support + against + 1)
    confidence = round(raw if counter_search_done else min(raw, UNSEARCHED_CAP), 3)
    explanation = [
        f"soutien {support} ({solid_support} preuve(s) CANON solide(s)), "
        f"contre {against} ({solid_against} solide(s))",
        f"confiance = {support} / ({support} + {against} + 1) = {round(raw, 3)}",
    ]
    if not counter_search_done:
        explanation.append(
            f"recherche de contre-preuves non faite : confiance plafonnée à {UNSEARCHED_CAP}"
        )
    level = "THEORY" if solid_support and counter_search_done else "SPECULATION"
    if level == "SPECULATION":
        explanation.append(
            "niveau SPECULATION : "
            + (
                "aucune preuve CANON solide"
                if not solid_support
                else "recherche de contre-preuves à faire"
            )
        )
    if support == 0 and against == 0:
        status = "OPEN"
    elif against > support and solid_against:
        status = "REFUTED"
    elif against > 0:
        status = "CONTESTED"
    else:
        status = "SUPPORTED"
    return Score(level, status, confidence, support, against, tuple(explanation))
