"""Routes Droits, mémoire éditoriale et coûts (ADR-0031)."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from primestone.memory import MemoryService

router = APIRouter(prefix="/memory", tags=["memory"])
Short = Annotated[str, Field(min_length=1, max_length=1000)]
Name = Annotated[str, Field(min_length=1, max_length=100)]


def _svc(request: Request) -> MemoryService:
    service: MemoryService = request.app.state.memory
    return service


def _call(fn: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return fn(*args, **kwargs)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None


class RightsIn(BaseModel):
    kind: Literal["PANEL_QUOTE", "IMAGE", "MUSIC", "VOICE", "VIDEO", "TEXT"]
    subject: Short
    source: Short
    basis: Literal["QUOTATION", "LICENSE", "PERMISSION", "OWN_WORK", "PUBLIC_DOMAIN"]
    proof: Short
    limits: Short
    script_id: UUID | None = None
    document_title: Name | None = None
    page_number: Annotated[int, Field(gt=0)] | None = None
    panel_number: Annotated[int, Field(gt=0)] | None = None
    license: Short | None = None
    expires_on: date | None = None
    recorded_by: Name = "propriétaire"


class WithdrawIn(BaseModel):
    record_id: UUID


class LessonIn(BaseModel):
    lesson: Short
    source_type: Literal["content_item", "experiment"]
    source_id: UUID
    series_id: UUID | None = None
    recorded_by: Name = "propriétaire"


class RetractIn(BaseModel):
    lesson_id: UUID
    reason: Short


@router.get("/rights")
def rights(request: Request, script_id: UUID | None = None) -> list[dict[str, Any]]:
    return _svc(request).rights(script_id)


@router.post("/rights", status_code=status.HTTP_201_CREATED)
def record_rights(request: Request, body: RightsIn) -> dict[str, str]:
    return {"record_id": str(_call(_svc(request).record_rights, **body.model_dump()))}


@router.post("/rights/withdrawals")
def withdraw(request: Request, body: WithdrawIn) -> dict[str, str]:
    _call(_svc(request).withdraw_rights, body.record_id)
    return {"status": "WITHDRAWN"}


@router.get("/rights/check/{script_id}")
def rights_check(request: Request, script_id: UUID) -> dict[str, Any]:
    return _svc(request).rights_check(script_id)


@router.get("/lessons")
def lessons(request: Request, series_id: UUID | None = None) -> list[dict[str, Any]]:
    return _svc(request).lessons(series_id)


@router.post("/lessons", status_code=status.HTTP_201_CREATED)
def record_lesson(request: Request, body: LessonIn) -> dict[str, Any]:
    data = body.model_dump()
    lesson = data.pop("lesson")
    result: dict[str, Any] = _call(_svc(request).record_lesson, lesson, **data)
    return result


@router.post("/lessons/retractions")
def retract(request: Request, body: RetractIn) -> dict[str, str]:
    _call(_svc(request).retract_lesson, body.lesson_id, reason=body.reason)
    return {"status": "RETRACTED"}


@router.get("/journal")
def journal(request: Request) -> list[dict[str, Any]]:
    return _svc(request).journal()


@router.get("/costs")
def costs(request: Request) -> dict[str, Any]:
    return _svc(request).costs()
