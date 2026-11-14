"""Routes du laboratoire des théories (coût nul). Écritures sur URLs fixes, identifiants dans le
corps validé."""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from primestone.lab import LabError, TheoryLab

router = APIRouter(prefix="/lab", tags=["lab"])

Name = Annotated[str, Field(min_length=1, max_length=100)]


def _lab(request: Request) -> TheoryLab:
    lab: TheoryLab = request.app.state.lab
    return lab


class TheoryIn(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=200)]
    claim: Annotated[str, Field(min_length=1, max_length=5000)]
    document_ids: Annotated[list[UUID], Field(min_length=1, max_length=200)]
    subjects: Annotated[list[Annotated[str, Field(max_length=200)]], Field(max_length=50)] = []
    author: Name = "propriétaire"


class EvidenceIn(BaseModel):
    theory_id: UUID
    role: Literal["SUPPORTS", "REFUTES"]
    document_id: UUID
    page: Annotated[int, Field(ge=1, le=10_000)]
    panel: Annotated[int, Field(ge=1, le=500)] | None = None
    excerpt: Annotated[str, Field(max_length=2000)] | None = None
    level: Literal["CANON", "INTERPRETATION", "SPECULATION"] = "CANON"
    note: Annotated[str, Field(max_length=2000)] | None = None
    author: Name = "propriétaire"


class RetractIn(BaseModel):
    evidence_id: UUID
    reason: Annotated[str, Field(min_length=1, max_length=2000)]
    author: Name = "propriétaire"


class AlternativeIn(BaseModel):
    theory_id: UUID
    text: Annotated[str, Field(min_length=1, max_length=2000)]
    author: Name = "propriétaire"


class ResearchIn(BaseModel):
    theory_id: UUID


def _call(fn: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return fn(*args, **kwargs)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from None
    except LabError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None


@router.post("/theories", status_code=status.HTTP_201_CREATED)
def create_theory(request: Request, body: TheoryIn) -> dict[str, str]:
    theory_id = _call(
        _lab(request).create,
        title=body.title,
        claim=body.claim,
        document_ids=body.document_ids,
        subjects=body.subjects,
        author=body.author,
    )
    return {"theory_id": str(theory_id)}


@router.get("/theories")
def theories(
    request: Request,
    status_: Annotated[
        Literal["OPEN", "SUPPORTED", "CONTESTED", "REFUTED"] | None, Query(alias="status")
    ] = None,
    level: Literal["THEORY", "SPECULATION"] | None = None,
) -> list[dict[str, Any]]:
    return _lab(request).theories(status=status_, level=level)


@router.get("/theories/{theory_id}")
def theory(request: Request, theory_id: UUID) -> dict[str, Any]:
    found = _lab(request).theory(theory_id)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "théorie introuvable")
    return found


@router.post("/evidence", status_code=status.HTTP_201_CREATED)
def add_evidence(request: Request, body: EvidenceIn) -> dict[str, Any]:
    """Ajoute une preuve ; un extrait absent de la page transcrite est refusé (422)."""
    result: dict[str, Any] = _call(
        _lab(request).add_evidence,
        body.theory_id,
        role=body.role,
        document_id=body.document_id,
        page=body.page,
        panel=body.panel,
        excerpt=body.excerpt,
        level=body.level,
        note=body.note,
        author=body.author,
    )
    return result


@router.post("/evidence/retractions", status_code=status.HTTP_201_CREATED)
def retract_evidence(request: Request, body: RetractIn) -> dict[str, Any]:
    result: dict[str, Any] = _call(
        _lab(request).retract_evidence, body.evidence_id, author=body.author, reason=body.reason
    )
    return result


@router.post("/alternatives", status_code=status.HTTP_201_CREATED)
def add_alternative(request: Request, body: AlternativeIn) -> dict[str, str]:
    alt_id = _call(
        _lab(request).add_alternative, body.theory_id, text_=body.text, author=body.author
    )
    return {"alternative_id": str(alt_id)}


@router.post("/research")
def research(request: Request, body: ResearchIn) -> dict[str, Any]:
    """Theory Researcher : candidats pour/contre (gratuit) ; marque la recherche faite."""
    result: dict[str, Any] = _call(_lab(request).research, body.theory_id)
    return result
