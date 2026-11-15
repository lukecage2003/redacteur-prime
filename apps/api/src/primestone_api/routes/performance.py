"""Routes Performance Intelligence : chaîne Primestone uniquement (coût nul)."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from primestone.performance import ImportError_, PerformanceError, PerformanceService

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
