"""Modèles de la vision : cases, zones de texte, analyse d'une page."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from primestone.provenance import BoundingBox

Confidence = Annotated[float, Field(ge=0.0, le=1.0)]


class ReadingDirection(StrEnum):
    LTR = "LTR"  # comics occidentaux, BD franco-belge
    RTL = "RTL"  # manga


class TextKind(StrEnum):
    DIALOGUE = "DIALOGUE"  # bulle de parole
    THOUGHT = "THOUGHT"  # bulle de pensée
    NARRATION = "NARRATION"  # récitatif, cartouche
    SFX = "SFX"  # onomatopée
    CAPTION = "CAPTION"  # légende, titre, crédit
    OTHER = "OTHER"  # texte dans le décor, signe, etc.


class Panel(BaseModel):
    model_config = ConfigDict(frozen=True)

    index: Annotated[int, Field(ge=1)]  # ordre de lecture
    bbox: BoundingBox


class TextRegion(BaseModel):
    """Texte repéré sur la page. `panel_index` est attribué par géométrie (None : hors case)."""

    text: Annotated[str, Field(min_length=1, max_length=5000)]
    kind: TextKind
    bbox: BoundingBox
    language: str | None = None  # "fr", "en", …
    confidence: Confidence = 1.0
    speaker: str | None = None  # personnage, s'il est identifiable
    speaker_confidence: Confidence | None = None
    panel_index: Annotated[int, Field(ge=1)] | None = None
    order: Annotated[int, Field(ge=1)] | None = None  # ordre de lecture dans la page
