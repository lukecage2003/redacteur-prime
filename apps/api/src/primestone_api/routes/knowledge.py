"""Routes Knowledge (entités, relations, corrections, graphe) et recherche hybride."""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from primestone.knowledge import KnowledgeError, KnowledgeService, ManualEvidence, hybrid_search
from primestone.provenance import EvidenceLevel

router = APIRouter(tags=["knowledge"])

Name = Annotated[str, Field(min_length=1, max_length=300)]
Reason = Annotated[str, Field(min_length=1, max_length=2000)]
EntityType = Literal[
    "CHARACTER", "EVENT", "LOCATION", "OBJECT", "CONCEPT", "SERIES", "CONTINUITY", "COMIC"
]
RelationType = Literal[
    "APPEARS_IN",
    "REFERENCES",
    "CONTRADICTS",
    "PRECEDES",
    "REVEALS",
    "FORESHADOWS",
    "RELATED_TO",
    "OPPOSES",
]


def _kb(request: Request) -> KnowledgeService:
    service: KnowledgeService = request.app.state.knowledge
    return service


class BuildRequest(BaseModel):
    document_ids: Annotated[list[UUID], Field(min_length=1, max_length=500)]


class CorrectionIn(BaseModel):
    action: Literal["rename", "add_alias", "merge", "retract_relation"]
    entity_id: UUID | None = None
    other_entity_id: UUID | None = None  # merge : entité absorbée
    relation_id: UUID | None = None
    value: Annotated[str, Field(max_length=300)] | None = None
    language: Annotated[str, Field(max_length=8)] | None = None
    reason: Reason
    author: Name = "propriétaire"


class EvidenceIn(BaseModel):
    document_id: UUID
    page: Annotated[int, Field(ge=1, le=100_000)]
    panel: Annotated[int, Field(ge=1)] | None = None
    excerpt: Annotated[str, Field(max_length=2000)] | None = None


class RelationIn(BaseModel):
    source_id: UUID
    target_id: UUID
    type: RelationType
    qualifier: Annotated[str, Field(max_length=300)] | None = None
    level: Literal["CANON", "INTERPRETATION", "SPECULATION"]
    evidence: Annotated[list[EvidenceIn], Field(min_length=1, max_length=50)]
    reason: Reason
    author: Name = "propriétaire"


@router.post("/knowledge/build", status_code=status.HTTP_201_CREATED)
def build(request: Request, body: BuildRequest) -> dict[str, int]:
    return _kb(request).build(body.document_ids)


@router.get("/knowledge/entities")
def entities(
    request: Request,
    type: EntityType | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> list[dict[str, Any]]:
    return _kb(request).entities(type_=type, query=q, limit=limit)


@router.get("/knowledge/entities/{entity_id}")
def entity(request: Request, entity_id: UUID) -> dict[str, Any]:
    found = _kb(request).entity(entity_id)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "entité introuvable")
    return found


@router.get("/knowledge/entities/{entity_id}/graph")
def graph(
    request: Request, entity_id: UUID, depth: Annotated[int, Query(ge=1, le=3)] = 1
) -> dict[str, Any]:
    try:
        return _kb(request).neighbors(entity_id, depth)
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "entité introuvable") from None


@router.get("/knowledge/path")
def path(request: Request, from_id: UUID, to_id: UUID) -> dict[str, Any]:
    try:
        steps = _kb(request).path(from_id, to_id)
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "entité introuvable") from None
    return {"found": steps is not None, "steps": steps or []}


@router.post("/knowledge/corrections", status_code=status.HTTP_201_CREATED)
def correct(request: Request, body: CorrectionIn) -> dict[str, str]:
    """Correction humaine journalisée (URL fixe : identifiants dans le corps validé)."""
    kb = _kb(request)
    try:
        if body.action == "retract_relation":
            if body.relation_id is None:
                raise KnowledgeError("relation_id requis")
            kb.retract_relation(body.relation_id, author=body.author, reason=body.reason)
        elif body.entity_id is None:
            raise KnowledgeError("entity_id requis")
        elif body.action == "merge":
            if body.other_entity_id is None:
                raise KnowledgeError("other_entity_id requis")
            kb.merge(body.entity_id, body.other_entity_id, author=body.author, reason=body.reason)
        elif not body.value:
            raise KnowledgeError("value requis")
        elif body.action == "rename":
            kb.rename(body.entity_id, body.value, author=body.author, reason=body.reason)
        else:
            kb.add_alias(
                body.entity_id,
                body.value,
                language=body.language,
                author=body.author,
                reason=body.reason,
            )
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from None
    except KnowledgeError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    return {"status": "ok"}


@router.post("/knowledge/relations", status_code=status.HTTP_201_CREATED)
def create_relation(request: Request, body: RelationIn) -> dict[str, str]:
    try:
        relation_id = _kb(request).create_relation(
            body.source_id,
            body.target_id,
            body.type,
            qualifier=body.qualifier,
            level=EvidenceLevel(body.level),
            evidence=[
                ManualEvidence(e.document_id, e.page, e.panel, e.excerpt) for e in body.evidence
            ],
            author=body.author,
            reason=body.reason,
        )
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from None
    except KnowledgeError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    return {"relation_id": str(relation_id)}


@router.get("/search")
def search(
    request: Request,
    q: Annotated[str, Query(min_length=1, max_length=500)],
    document_ids: Annotated[list[UUID] | None, Query(max_length=500)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[dict[str, Any]]:
    kb = _kb(request)
    return hybrid_search(
        request.app.state.engine, kb.embedder, q, document_ids=document_ids, limit=limit
    )
