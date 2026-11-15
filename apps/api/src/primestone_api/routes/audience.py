"""Routes Audience Intelligence & communauté (coût nul, aucune donnée personnelle)."""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from primestone.audience import AudienceError, AudienceService

router = APIRouter(prefix="/audience", tags=["audience"])
Short = Annotated[str, Field(min_length=1, max_length=300)]


def _svc(request: Request) -> AudienceService:
    service: AudienceService = request.app.state.audience
    return service


def _call(fn: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return fn(*args, **kwargs)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from None
    except AudienceError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None


class SegmentIn(BaseModel):
    name: Short
    description: Annotated[str, Field(min_length=1, max_length=2000)]
    motivations: Annotated[list[Short], Field(min_length=1, max_length=20)]
    knowledge_level: Literal["NOVICE", "INTERMEDIATE", "EXPERT"] | None = None
    author: Annotated[str, Field(min_length=1, max_length=100)] = "propriétaire"


class EvidenceIn(BaseModel):
    segment_id: UUID
    kind: Literal["METRIC", "COMMENT_CLUSTER", "MARKET", "DECLARED"]
    statement: Annotated[str, Field(min_length=1, max_length=2000)]
    data: dict[str, Any] = {}
    data_class: Literal["PUBLIC", "PRIVATE_AUTHORIZED", "ESTIMATE", "HYPOTHESIS"] = "PUBLIC"
    author: Annotated[str, Field(min_length=1, max_length=100)] = "propriétaire"


class LinkIn(BaseModel):
    segment_id: UUID
    target_kind: Literal["ENTITY", "TOPIC", "FORMAT", "PLATFORM"]
    target: Short
    relation: Literal["INTERESTED_IN", "PREFERS", "USES", "ASKS_ABOUT", "FRUSTRATED_BY"]
    evidence_id: UUID


class CommentIn(BaseModel):
    """Commentaire public, sans identité d'auteur (champs inconnus refusés)."""

    model_config = {"extra": "forbid"}
    external_id: Annotated[str, Field(min_length=1, max_length=200)]
    text: Annotated[str, Field(min_length=1, max_length=5000)]
    like_count: Annotated[int, Field(ge=0)] = 0
    published_at: Annotated[str, Field(max_length=40)] | None = None
    language: Literal["fr", "en"] | None = None


class CommentsIn(BaseModel):
    platform: Literal["youtube", "tiktok", "instagram", "other"]
    content_id: UUID | None = None
    comments: Annotated[list[CommentIn], Field(min_length=1, max_length=5000)]


@router.get("/segments")
def segments(request: Request) -> list[dict[str, Any]]:
    return _svc(request).segments()


@router.post("/segments", status_code=status.HTTP_201_CREATED)
def create_segment(request: Request, body: SegmentIn) -> dict[str, str]:
    segment_id = _call(
        _svc(request).create_segment,
        name=body.name,
        description=body.description,
        motivations=body.motivations,
        knowledge_level=body.knowledge_level,
        author=body.author,
    )
    return {"segment_id": str(segment_id)}


@router.post("/evidence", status_code=status.HTTP_201_CREATED)
def add_evidence(request: Request, body: EvidenceIn) -> dict[str, str]:
    result: dict[str, str] = _call(
        _svc(request).add_evidence,
        body.segment_id,
        kind=body.kind,
        statement=body.statement,
        data=body.data,
        data_class=body.data_class,
        author=body.author,
    )
    return result


@router.post("/links", status_code=status.HTTP_201_CREATED)
def link(request: Request, body: LinkIn) -> dict[str, str]:
    _call(
        _svc(request).link,
        body.segment_id,
        target_kind=body.target_kind,
        target=body.target,
        relation=body.relation,
        evidence_id=body.evidence_id,
    )
    return {"status": "ok"}


@router.post("/comments", status_code=status.HTTP_201_CREATED)
def import_comments(request: Request, body: CommentsIn) -> dict[str, int]:
    result: dict[str, int] = _svc(request).import_comments(
        [c.model_dump() for c in body.comments], platform=body.platform, content_id=body.content_id
    )
    return result


@router.get("/community")
def community(request: Request) -> dict[str, Any]:
    return _svc(request).community()
