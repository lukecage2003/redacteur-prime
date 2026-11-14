"""Provenance et niveaux d'évidence — règles transverses à toutes les intelligences.

Invariants (voir DATA_MODEL.md) :
- toute observation est rattachée à au moins une référence documentaire exacte ;
- CANON, INTERPRETATION, THEORY et SPECULATION ne se mélangent jamais ;
- toute théorie expose preuves, contre-preuves, alternatives et confiance ;
- une analyse n'est jamais complète s'il manque des pages ;
- les données de marché sont classées (public, privé autorisé, estimation, hypothèse).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

Confidence = Annotated[float, Field(ge=0.0, le=1.0)]


class EvidenceLevel(StrEnum):
    """Statut épistémique d'une affirmation sur une œuvre."""

    CANON = "CANON"  # explicitement montré ou dit dans l'œuvre
    INTERPRETATION = "INTERPRETATION"  # lecture argumentée d'éléments canoniques
    THEORY = "THEORY"  # hypothèse structurée, avec preuves et contre-preuves
    SPECULATION = "SPECULATION"  # piste faiblement étayée


class DataClass(StrEnum):
    """Nature d'une donnée de marché ou de performance."""

    PUBLIC = "PUBLIC"
    PRIVATE_AUTHORIZED = "PRIVATE_AUTHORIZED"  # comptes Primestone connectés via OAuth
    ESTIMATE = "ESTIMATE"
    HYPOTHESIS = "HYPOTHESIS"


class BoundingBox(BaseModel):
    """Zone d'une page en coordonnées normalisées [0, 1] (indépendantes de la résolution)."""

    model_config = ConfigDict(frozen=True)

    x: Confidence
    y: Confidence
    width: Annotated[float, Field(gt=0.0, le=1.0)]
    height: Annotated[float, Field(gt=0.0, le=1.0)]

    @model_validator(mode="after")
    def _inside_page(self) -> Self:
        if self.x + self.width > 1.0 + 1e-9 or self.y + self.height > 1.0 + 1e-9:
            raise ValueError("la zone dépasse les limites de la page")
        return self


class DocumentRef(BaseModel):
    """Référence documentaire exacte : document, page, case éventuelle, zone, extrait."""

    model_config = ConfigDict(frozen=True)

    document_id: UUID
    page: Annotated[int, Field(ge=1)]
    panel: Annotated[int, Field(ge=1)] | None = None
    bbox: BoundingBox | None = None
    excerpt: Annotated[str, Field(max_length=2000)] | None = None


class Observation(BaseModel):
    """Affirmation sur une œuvre, toujours prouvée par au moins une référence."""

    statement: Annotated[str, Field(min_length=1)]
    level: EvidenceLevel
    confidence: Confidence
    evidence: Annotated[list[DocumentRef], Field(min_length=1)]

    @model_validator(mode="after")
    def _theory_is_not_an_observation(self) -> Self:
        if self.level is EvidenceLevel.THEORY:
            raise ValueError("une théorie doit être modélisée avec `Theory`, pas `Observation`")
        return self


class Theory(BaseModel):
    """Théorie : preuves, contre-preuves, alternatives et confiance sont obligatoires."""

    title: Annotated[str, Field(min_length=1)]
    claim: Annotated[str, Field(min_length=1)]
    level: EvidenceLevel = EvidenceLevel.THEORY
    confidence: Confidence
    supporting: Annotated[list[DocumentRef], Field(min_length=1)]
    counter_evidence: list[DocumentRef]
    alternatives: list[str]
    counter_evidence_searched: bool = Field(
        description="Vrai si la recherche de contre-preuves a été effectuée, même sans résultat."
    )

    @model_validator(mode="after")
    def _rigor(self) -> Self:
        if self.level not in (EvidenceLevel.THEORY, EvidenceLevel.SPECULATION):
            raise ValueError("une théorie est de niveau THEORY ou SPECULATION")
        if not self.counter_evidence_searched:
            raise ValueError("la recherche de contre-preuves est obligatoire")
        if not self.alternatives:
            raise ValueError("au moins une explication alternative est obligatoire")
        return self


def missing_pages(expected_page_count: int, processed_pages: set[int]) -> list[int]:
    """Pages attendues (1..N) non traitées. Une liste non vide interdit le statut COMPLETE."""
    if expected_page_count < 0:
        raise ValueError("expected_page_count doit être positif")
    return [p for p in range(1, expected_page_count + 1) if p not in processed_pages]


def is_analysis_complete(expected_page_count: int, processed_pages: set[int]) -> bool:
    return expected_page_count > 0 and not missing_pages(expected_page_count, processed_pages)
