"""Routes Comic Vision (/api/v1/vision et analyse de page)."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from primestone.vision import ReadingDirection
from primestone.vision.service import VisionBudgetError, VisionService

router = APIRouter(tags=["vision"])


class AnalysisRequest(BaseModel):
    document_ids: Annotated[list[UUID], Field(min_length=1, max_length=500)]
    provider: str = "fake"
    budget_usd: Annotated[Decimal, Field(ge=0, le=1000)]
    direction: ReadingDirection = ReadingDirection.LTR
    language_hint: Annotated[str | None, Field(max_length=8)] = None


def _service(request: Request) -> VisionService:
    service: VisionService = request.app.state.vision
    return service


def _check_provider(service: VisionService, name: str) -> None:
    try:
        service.provider(name)
    except LookupError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from None


@router.post("/vision/estimates")
def estimate(request: Request, body: AnalysisRequest) -> dict[str, Any]:
    """Estimation du coût, sans rien lancer."""
    service = _service(request)
    _check_provider(service, body.provider)
    result, _ = service.estimate(body.document_ids, body.provider, body.budget_usd, body.direction)
    return result.as_dict()


@router.post("/vision/analyses", status_code=status.HTTP_202_ACCEPTED)
def create_analysis(request: Request, body: AnalysisRequest) -> dict[str, Any]:
    """Lance l'analyse si l'estimation tient dans le budget (sinon 422 avec l'estimation)."""
    service = _service(request)
    _check_provider(service, body.provider)
    try:
        run_id, result = service.start(
            body.document_ids,
            body.provider,
            body.budget_usd,
            direction=body.direction,
            language_hint=body.language_hint,
        )
    except VisionBudgetError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {"message": str(exc), "estimate": exc.estimate.as_dict()},
        ) from None
    return {"run_id": str(run_id), "estimate": result.as_dict()}


@router.get("/vision/analyses/{run_id}")
def get_analysis_run(request: Request, run_id: UUID) -> dict[str, Any]:
    report = _service(request).run_report(run_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "lot introuvable")
    return report


@router.get("/library/documents/{document_id}/pages/{number}/analysis")
def get_page_analysis(request: Request, document_id: UUID, number: int) -> dict[str, Any]:
    analysis = _service(request).latest_analysis(document_id, number)
    if analysis is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "aucune analyse pour cette page")
    return analysis
