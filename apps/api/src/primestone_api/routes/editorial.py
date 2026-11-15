"""Routes Editorial Director : agents, missions, décisions humaines (coût nul)."""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from primestone.editorial import EditorialError, EditorialService

router = APIRouter(prefix="/editorial", tags=["editorial"])


def _editorial(request: Request) -> EditorialService:
    service: EditorialService = request.app.state.editorial
    return service


class MissionIn(BaseModel):
    type: Literal[
        "CHARACTER_DOSSIER",
        "CONTINUITY_AUDIT",
        "FACT_CHECK",
        "THEORY_REVIEW",
        "RESEARCH_DOSSIER",
        "MARKET_BRIEF",
        "SOCIAL_PACKAGE",
        "SCRIPT_REVIEW",
        "PERFORMANCE_REVIEW",
        "AUDIENCE_BRIEF",
        "OPPORTUNITY_BRIEF",
        "PACKAGING_REVIEW",
        "VIDEO_AUTOPSY",
    ]
    # Vide pour une revue de théorie : les documents de la théorie sont repris.
    document_ids: Annotated[list[UUID], Field(max_length=200)] = []
    theory_id: UUID | None = None
    question: Annotated[str, Field(max_length=500)] | None = None
    source_mission_id: UUID | None = None
    script_id: UUID | None = None
    content_id: UUID | None = None
    platforms: (
        list[Literal["youtube_long", "tiktok", "instagram_reels", "instagram_carousel"]] | None
    ) = None
    character: Annotated[str, Field(max_length=200)] | None = None
    draft: Annotated[str, Field(max_length=50_000)] | None = None
    known_characters: Annotated[
        list[Annotated[str, Field(max_length=200)]], Field(max_length=200)
    ] = []
    title: Annotated[str, Field(max_length=200)] | None = None


class DecisionIn(BaseModel):
    approval_id: UUID
    decision: Literal["approve", "reject"]
    comment: Annotated[str, Field(max_length=2000)] | None = None
    author: Annotated[str, Field(min_length=1, max_length=100)] = "propriétaire"


@router.get("/agents")
def agents(request: Request) -> list[dict[str, Any]]:
    return _editorial(request).agents()


@router.post("/missions", status_code=status.HTTP_202_ACCEPTED)
def create_mission(request: Request, body: MissionIn) -> dict[str, str]:
    params: dict[str, Any] = {"known_characters": body.known_characters}
    if body.character:
        params["character"] = body.character
    if body.draft:
        params["draft"] = body.draft
    if body.theory_id:
        params["theory_id"] = str(body.theory_id)
    if body.question:
        params["question"] = body.question
    if body.source_mission_id:
        params["source_mission_id"] = str(body.source_mission_id)
    if body.script_id:
        params["script_id"] = str(body.script_id)
    if body.content_id:
        params["content_id"] = str(body.content_id)
    if body.platforms:
        params["platforms"] = body.platforms
    try:
        mission_id = _editorial(request).create_mission(
            body.type, body.document_ids, params, title=body.title
        )
    except EditorialError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    return {"mission_id": str(mission_id)}


@router.get("/missions")
def missions(request: Request) -> list[dict[str, Any]]:
    return _editorial(request).missions()


@router.get("/missions/{mission_id}")
def mission(request: Request, mission_id: UUID) -> dict[str, Any]:
    try:
        return _editorial(request).mission(mission_id)
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "mission introuvable") from None


@router.post("/approvals", status_code=status.HTTP_201_CREATED)
def decide(request: Request, body: DecisionIn) -> dict[str, str]:
    """Décision humaine (URL fixe). Un livrable avec erreur factuelle majeure ne peut pas être
    approuvé (422)."""
    try:
        _editorial(request).decide(
            body.approval_id,
            approve=body.decision == "approve",
            author=body.author,
            comment=body.comment,
        )
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from None
    except EditorialError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    return {"status": "ok"}
