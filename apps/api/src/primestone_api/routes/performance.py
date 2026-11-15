"""Routes Performance Intelligence : chaîne Primestone uniquement (coût nul)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from primestone.performance import (
    ImportError_,
    PerformanceError,
    PerformanceLab,
    PerformanceService,
)

router = APIRouter(prefix="/performance", tags=["performance"])


def _svc(request: Request) -> PerformanceService:
    service: PerformanceService = request.app.state.performance
    return service


class StudioImportIn(BaseModel):
    """Contenu texte d'un export CSV de YouTube Studio (chaîne du propriétaire)."""

    csv: Annotated[str, Field(min_length=1, max_length=5_000_000)]
    period_start: date | None = None
    period_end: date | None = None
    author: Annotated[str, Field(min_length=1, max_length=100)] = "propriétaire"


class LinkIn(BaseModel):
    content_id: UUID
    script_id: UUID
    language: Literal["fr", "en"] | None = None


@router.post("/imports", status_code=status.HTTP_201_CREATED)
def import_studio(request: Request, body: StudioImportIn) -> dict[str, Any]:
    try:
        return _svc(request).import_studio_csv(
            body.csv, author=body.author, period=(body.period_start, body.period_end)
        )
    except (ImportError_, PerformanceError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None


@router.post("/links", status_code=status.HTTP_201_CREATED)
def link(request: Request, body: LinkIn) -> dict[str, str]:
    try:
        _svc(request).link_script(body.content_id, body.script_id, language=body.language)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from None
    return {"status": "ok"}


@router.get("/contents")
def contents(request: Request) -> list[dict[str, Any]]:
    return _svc(request).contents()


@router.get("/report")
def report(request: Request, min_items: Annotated[int, Query(ge=3, le=1000)] = 5) -> dict[str, Any]:
    return _svc(request).report(min_items=min_items)


# --- Phase 14 : objectifs, rétention, expériences, synchronisation autorisée -------------------

Objective = Literal["DISCOVERY", "EXPLORATION", "EXPERTISE", "COMMUNITY"]
Format = Literal["LONG", "SHORT", "REEL", "CAROUSEL", "POST", "PODCAST", "LIVE"]
Variable = Literal["TITLE", "THUMBNAIL", "HOOK", "PROMISE", "FORMAT", "LENGTH", "OTHER"]
Text_ = Annotated[str, Field(min_length=1, max_length=2000)]


class ObjectiveIn(BaseModel):
    content_id: UUID
    objective: Objective | None = None
    format: Format | None = None


class ExperimentIn(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=300)]
    hypothesis: Text_
    variable: Variable
    metric: Annotated[str, Field(min_length=1, max_length=50)]
    audience: Annotated[str, Field(max_length=300)] | None = None
    format: Format | None = None
    content_ids: Annotated[list[UUID], Field(max_length=50)] = []
    period_start: date | None = None
    period_end: date | None = None
    author: Annotated[str, Field(min_length=1, max_length=100)] = "propriétaire"


class VariantIn(BaseModel):
    experiment_id: UUID
    label: Annotated[str, Field(min_length=1, max_length=20)]
    description: Text_
    exposures: Annotated[int, Field(ge=0)] | None = None
    successes: Annotated[int, Field(ge=0)] | None = None
    reported_share: Annotated[Decimal, Field(ge=0, le=1)] | None = None
    source: Literal["MANUAL", "YOUTUBE_TEST_COMPARE", "YOUTUBE_ANALYTICS_API"] = "MANUAL"


class ConclusionIn(BaseModel):
    experiment_id: UUID
    conclusion: Annotated[str, Field(max_length=2000)] | None = None
    next_experiment: Annotated[str, Field(max_length=2000)] | None = None


def _guard(fn: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return fn(*args, **kwargs)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from None
    except PerformanceError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None


@router.post("/objectives", status_code=status.HTTP_201_CREATED)
def set_objective(request: Request, body: ObjectiveIn) -> dict[str, str]:
    _guard(
        _svc(request).set_objective, body.content_id, objective=body.objective, format_=body.format
    )
    return {"status": "ok"}


@router.get("/objectives-report")
def objectives_report(request: Request) -> dict[str, Any]:
    return _svc(request).objective_report()


@router.get("/contents/{content_id}/retention")
def retention(request: Request, content_id: UUID) -> list[dict[str, Any]]:
    return _svc(request).retention(content_id)


@router.get("/experiments")
def experiments(request: Request) -> list[dict[str, Any]]:
    return _svc(request).experiments()


@router.post("/experiments", status_code=status.HTTP_201_CREATED)
def create_experiment(request: Request, body: ExperimentIn) -> dict[str, str]:
    experiment_id = _guard(
        _svc(request).create_experiment,
        title=body.title,
        hypothesis=body.hypothesis,
        variable=body.variable,
        metric=body.metric,
        author=body.author,
        audience=body.audience,
        format_=body.format,
        content_ids=body.content_ids,
        period=(body.period_start, body.period_end),
    )
    return {"experiment_id": str(experiment_id)}


@router.post("/experiments/variants", status_code=status.HTTP_201_CREATED)
def add_variant(request: Request, body: VariantIn) -> dict[str, str]:
    _guard(
        _svc(request).add_variant,
        body.experiment_id,
        label=body.label,
        description=body.description,
        exposures=body.exposures,
        successes=body.successes,
        reported_share=body.reported_share,
        source=body.source,
    )
    return {"status": "ok"}


@router.post("/experiments/conclusions", status_code=status.HTTP_201_CREATED)
def conclude(request: Request, body: ConclusionIn) -> dict[str, Any]:
    result: dict[str, Any] = _guard(
        _svc(request).conclude,
        body.experiment_id,
        conclusion=body.conclusion,
        next_experiment=body.next_experiment,
    )
    return result


# --- Phase 19 : Content Performance Lab ------------------------------------------------------


def _lab(request: Request) -> PerformanceLab:
    return PerformanceLab(_svc(request).engine)


@router.get("/lab/autopsy/{content_id}")
def autopsy(request: Request, content_id: UUID) -> dict[str, Any]:
    try:
        return _lab(request).autopsy(content_id)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from None


@router.get("/lab/hooks")
def hooks(request: Request) -> dict[str, Any]:
    return _lab(request).hooks()


@router.get("/lab/drop-offs")
def drop_offs(request: Request) -> dict[str, Any]:
    return _lab(request).drop_offs()


@router.get("/lab/returning")
def returning(request: Request) -> dict[str, Any]:
    return _lab(request).returning()


@router.get("/lab/loop/{script_id}")
def loop(request: Request, script_id: UUID) -> dict[str, Any]:
    try:
        return _lab(request).loop(script_id)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from None


@router.get("/lab/validation")
def validation(request: Request) -> dict[str, Any]:
    """Les 13 critères de l'extension, démontrés ou non sur les données réelles."""
    return _lab(request).validation()
