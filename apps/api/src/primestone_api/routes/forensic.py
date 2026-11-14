"""Routes forensiques et transcription humaine (gratuites)."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from primestone.forensic import ForensicService
from primestone.vision import ReadingDirection, TextKind
from primestone.vision.service import HumanText, VisionService

router = APIRouter(tags=["forensic"])


class HumanTextIn(BaseModel):
    text: Annotated[str, Field(min_length=1, max_length=5000)]
    kind: TextKind = TextKind.DIALOGUE
    panel_index: Annotated[int, Field(ge=1)] | None = None
    speaker: Annotated[str, Field(max_length=200)] | None = None
    language: Annotated[str, Field(max_length=8)] | None = None


class TranscriptionIn(BaseModel):
    texts: Annotated[list[HumanTextIn], Field(max_length=300)]
    author: Annotated[str, Field(min_length=1, max_length=100)] = "propriétaire"
    direction: ReadingDirection = ReadingDirection.LTR


class TranscriptionByIdIn(TranscriptionIn):
    document_id: UUID
    page: Annotated[int, Field(ge=1, le=100_000)]


class ForensicRequest(BaseModel):
    document_ids: Annotated[list[UUID], Field(min_length=1, max_length=500)]
    known_characters: Annotated[
        list[Annotated[str, Field(max_length=200)]], Field(max_length=500)
    ] = []


DocumentIds = Annotated[list[UUID], Query(min_length=1, max_length=500)]


def _forensic(request: Request) -> ForensicService:
    service: ForensicService = request.app.state.forensic
    return service


@router.put(
    "/library/documents/{document_id}/pages/{number}/transcription",
    status_code=status.HTTP_201_CREATED,
)
def save_transcription(
    request: Request, document_id: UUID, number: int, body: TranscriptionIn
) -> dict[str, Any]:
    """Transcription saisie ou corrigée par un humain : nouvelle version servie (coût nul),
    les versions précédentes restent en base."""
    return _save(request, document_id, number, body)


@router.post("/transcriptions", status_code=status.HTTP_201_CREATED)
def save_transcription_by_body(request: Request, body: TranscriptionByIdIn) -> dict[str, Any]:
    """Même opération, URL fixe : l'identifiant et la page voyagent dans le corps validé."""
    return _save(request, body.document_id, body.page, body)


def _save(
    request: Request, document_id: UUID, number: int, body: TranscriptionIn
) -> dict[str, Any]:
    vision: VisionService = request.app.state.vision
    entries = [
        HumanText(
            text=t.text,
            kind=t.kind,
            panel_index=t.panel_index,
            speaker=(t.speaker or "").strip() or None,
            language=t.language,
        )
        for t in body.texts
    ]
    try:
        analysis_id = vision.save_human_transcription(
            document_id, number, entries, author=body.author, direction=body.direction
        )
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    return {"analysis_id": str(analysis_id)}


@router.post("/forensic/analyses", status_code=status.HTTP_201_CREATED)
def analyze(request: Request, body: ForensicRequest) -> dict[str, Any]:
    run_id, stats = _forensic(request).analyze(body.document_ids, set(body.known_characters))
    return {"run_id": str(run_id), **stats}


@router.get("/forensic/report")
def report(request: Request, document_ids: DocumentIds) -> dict[str, Any]:
    return _forensic(request).report(document_ids)


@router.get("/forensic/observations")
def observations(
    request: Request,
    document_ids: DocumentIds,
    kind: str | None = None,
    level: str | None = None,
    subject: str | None = None,
    limit: Annotated[int, Query(ge=1, le=2000)] = 500,
) -> list[dict[str, Any]]:
    return _forensic(request).observations(
        document_ids, kind=kind, level=level, subject=subject, limit=limit
    )
