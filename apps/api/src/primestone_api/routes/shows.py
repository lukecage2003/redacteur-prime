"""Routes du moteur d'émissions (ADR-0028) : chaque transition, chaque changement de règles
et chaque validation finale d'épisode crée une décision soumise au fondateur
(`/governance/decide`). Aucune route ne publie quoi que ce soit."""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from primestone.shows import ShowService

router = APIRouter(prefix="/shows", tags=["shows"])
Short = Annotated[str, Field(min_length=1, max_length=500)]
Name = Annotated[str, Field(min_length=1, max_length=100)]
Status = Literal["DRAFT", "TESTING", "ACTIVE", "SUSPENDED", "RETIRED"]


def _svc(request: Request) -> ShowService:
    service: ShowService = request.app.state.shows
    return service


def _call(fn: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return fn(*args, **kwargs)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from None
    except ValueError as exc:  # ShowError, GovernanceError
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None


class TransitionIn(BaseModel):
    series_id: UUID
    to: Status
    reason: Annotated[str, Field(max_length=2000)] | None = None
    proposed_by: Name = "propriétaire"


class GuidelinesIn(BaseModel):
    series_id: UUID
    changes: dict[str, Any]
    author: Name = "propriétaire"


class FormatIn(BaseModel):
    series_id: UUID
    name: Short
    platform: Name
    language: Literal["fr", "en"]
    min_minutes: Annotated[float, Field(gt=0, le=600)]
    max_minutes: Annotated[float, Field(gt=0, le=600)]
    structure: Annotated[list[Short], Field(min_length=1, max_length=30)]
    rules: dict[str, Any] = {}


class EpisodeStepIn(BaseModel):
    series_id: UUID
    number: Annotated[int, Field(gt=0)]
    step: Literal["production", "final-validation", "published"]
    content_id: UUID | None = None
    proposed_by: Name = "propriétaire"


@router.get("/fit")
def fit(
    request: Request,
    subject: Annotated[str, Query(min_length=3, max_length=300)],
    language: Literal["fr", "en"] | None = None,
) -> dict[str, Any]:
    """Adéquation d'un sujet aux émissions ouvertes et aux piliers actifs."""
    return _svc(request).fit(subject, language=language)


@router.get("/{series_id}")
def show(request: Request, series_id: UUID) -> dict[str, Any]:
    result: dict[str, Any] = _call(_svc(request).show, series_id)
    return result


@router.get("/{series_id}/guidelines")
def guidelines(request: Request, series_id: UUID) -> list[dict[str, Any]]:
    return _svc(request).guidelines(series_id)


@router.get("/{series_id}/performance")
def performance(request: Request, series_id: UUID) -> dict[str, Any]:
    return _svc(request).performance(series_id)


@router.post("/transitions", status_code=status.HTTP_201_CREATED)
def transition(request: Request, body: TransitionIn) -> dict[str, Any]:
    result: dict[str, Any] = _call(
        _svc(request).transition,
        body.series_id,
        body.to,
        proposed_by=body.proposed_by,
        reason=body.reason,
    )
    return result


@router.post("/guidelines", status_code=status.HTTP_201_CREATED)
def propose_guidelines(request: Request, body: GuidelinesIn) -> dict[str, Any]:
    result: dict[str, Any] = _call(
        _svc(request).propose_guidelines, body.series_id, body.changes, author=body.author
    )
    return result


@router.post("/formats", status_code=status.HTTP_201_CREATED)
def add_format(request: Request, body: FormatIn) -> dict[str, str]:
    data = body.model_dump()
    series_id = data.pop("series_id")
    return {"format_id": str(_call(_svc(request).add_format, series_id, **data))}


@router.post("/episodes/steps")
def episode_step(request: Request, body: EpisodeStepIn) -> dict[str, Any]:
    svc = _svc(request)
    if body.step == "production":
        _call(svc.start_production, body.series_id, body.number)
        return {"status": "IN_PRODUCTION"}
    if body.step == "final-validation":
        result: dict[str, Any] = _call(
            svc.propose_final_validation,
            body.series_id,
            body.number,
            proposed_by=body.proposed_by,
        )
        return result
    if body.content_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "content_id requis")
    _call(svc.declare_published, body.series_id, body.number, body.content_id)
    return {"status": "PUBLISHED"}
