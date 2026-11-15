"""Routes Identité indépendante (ADR-0029) : voix de marque sous licence, profils visuels par
langue, plan de narration. Aucune voix ni aucun visage du fondateur n'est requis."""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from primestone.identity import IdentityError, IdentityService

router = APIRouter(prefix="/identity", tags=["identity"])
Short = Annotated[str, Field(min_length=1, max_length=500)]
Name = Annotated[str, Field(min_length=1, max_length=100)]
Lang = Literal["fr", "en"]


def _svc(request: Request) -> IdentityService:
    service: IdentityService = request.app.state.identity
    return service


class VoiceIn(BaseModel):
    name: Name
    language: Lang
    tone: Short
    kind: Literal["SYNTHETIC", "HUMAN_LICENSED"] = "SYNTHETIC"
    provider: Name
    voice: Short
    license: Annotated[str, Field(min_length=1, max_length=2000)]
    license_url: Annotated[str, Field(max_length=1000)] | None = None
    allowed_use: Short
    consent_reference: Annotated[str, Field(max_length=1000)] | None = None
    proposed_by: Name = "propriétaire"


class VisualIn(BaseModel):
    rules: dict[str, Any]
    series_id: UUID | None = None
    platform: Name | None = None
    language: Lang | None = None
    created_by: Name = "propriétaire"


class NarrationIn(BaseModel):
    script_id: UUID


@router.get("/voices")
def voices(request: Request, language: Lang | None = None) -> list[dict[str, Any]]:
    return _svc(request).voices(language)


@router.post("/voices", status_code=status.HTTP_201_CREATED)
def propose_voice(request: Request, body: VoiceIn) -> dict[str, Any]:
    try:
        return _svc(request).propose_voice(**body.model_dump())
    except IdentityError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None


@router.get("/visuals")
def visuals(request: Request) -> list[dict[str, Any]]:
    return _svc(request).visuals()


@router.get("/visuals/resolve")
def resolve_visual(
    request: Request,
    language: Annotated[Lang, Query()],
    series_id: UUID | None = None,
    platform: Annotated[str | None, Query(max_length=100)] = None,
) -> dict[str, Any]:
    return _svc(request).visual_for(language=language, series_id=series_id, platform=platform)


@router.post("/visuals", status_code=status.HTTP_201_CREATED)
def add_visual(request: Request, body: VisualIn) -> dict[str, Any]:
    data = body.model_dump()
    rules = data.pop("rules")
    try:
        return _svc(request).add_visual(rules, **data)
    except IdentityError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None


@router.post("/narrations")
def narration(request: Request, body: NarrationIn) -> dict[str, Any]:
    """Plan de narration par la voix de marque (synthèse audio : CLI, modèle local)."""
    try:
        return _svc(request).narrate(body.script_id)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from None
    except IdentityError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
