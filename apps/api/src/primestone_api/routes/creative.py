"""Routes Creative Intelligence : charte, séries, packaging (coût nul)."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from primestone.creative import CreativeError, CreativeService

router = APIRouter(prefix="/creative", tags=["creative"])
Short = Annotated[str, Field(min_length=1, max_length=500)]
Name = Annotated[str, Field(min_length=1, max_length=100)]


def _svc(request: Request) -> CreativeService:
    service: CreativeService = request.app.state.creative
    return service


class CharterIn(BaseModel):
    name: Short
    rules: dict[str, Any]
    note: Annotated[str, Field(max_length=2000)] | None = None
    author: Name = "propriétaire"


class SeriesIn(BaseModel):
    name: Short
    promise: Short
    identity: Short
    tone: Short
    structure: Annotated[list[Short], Field(min_length=1, max_length=20)]
    target_minutes: Annotated[int, Field(gt=0, le=240)]
    art_direction: Short
    distribution: Annotated[list[Short], Field(max_length=20)] = []
    evolution: Short
    segment_id: UUID | None = None
    author: Name = "propriétaire"


class EpisodeIn(BaseModel):
    series_id: UUID
    script_id: UUID


class PackagingIn(BaseModel):
    script_id: UUID


@router.get("/charter")
def charter(request: Request) -> dict[str, Any]:
    return _svc(request).charter()


@router.post("/charter", status_code=status.HTTP_201_CREATED)
def publish_charter(request: Request, body: CharterIn) -> dict[str, int]:
    try:
        version = _svc(request).publish_charter(
            body.rules, name=body.name, author=body.author, note=body.note
        )
    except CreativeError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    return {"version": version}


@router.get("/series")
def list_series(request: Request) -> list[dict[str, Any]]:
    return _svc(request).series()


@router.post("/series", status_code=status.HTTP_201_CREATED)
def create_series(request: Request, body: SeriesIn) -> dict[str, str]:
    try:
        series_id = _svc(request).create_series(**body.model_dump())
    except CreativeError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    return {"series_id": str(series_id)}


@router.post("/series/episodes", status_code=status.HTTP_201_CREATED)
def add_episode(request: Request, body: EpisodeIn) -> dict[str, int]:
    try:
        number = _svc(request).add_episode(body.series_id, body.script_id)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from None
    except CreativeError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    return {"episode": number}


@router.post("/packaging", status_code=status.HTTP_201_CREATED)
async def package(request: Request, body: PackagingIn) -> dict[str, Any]:
    """10 titres, 5 miniatures, 3 promesses, 3 accroches, contrôles, tests proposés."""
    try:
        return await _svc(request).package(body.script_id)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from None
    except CreativeError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None


@router.get("/packaging/{script_id}")
def packagings(request: Request, script_id: UUID) -> list[dict[str, Any]]:
    return _svc(request).packagings(script_id)
