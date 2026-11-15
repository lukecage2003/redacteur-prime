"""Routes Maximum Storytelling (coût nul). Écritures sur URLs fixes, identifiants dans le corps."""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from primestone.db.schema import SCRIPT_STEPS
from primestone.storytelling import ScriptError, StorytellingService, propose, techniques

router = APIRouter(prefix="/scripts", tags=["scripts"])

Name = Annotated[str, Field(min_length=1, max_length=100)]
Content = Annotated[str, Field(min_length=1, max_length=400_000)]


def _svc(request: Request) -> StorytellingService:
    service: StorytellingService = request.app.state.storytelling
    return service


def _call(fn: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return fn(*args, **kwargs)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from None
    except ScriptError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None


class ScriptIn(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=300)]
    language: Literal["fr", "en"]
    content: Annotated[str, Field(max_length=400_000)] = ""
    document_ids: Annotated[list[UUID], Field(max_length=200)] = []
    author: Name = "propriétaire"


class VersionIn(BaseModel):
    script_id: UUID
    content: Content
    author: Name = "propriétaire"


class StepIn(BaseModel):
    script_id: UUID
    step: Literal[SCRIPT_STEPS]  # type: ignore[valid-type]
    reason: Annotated[str, Field(max_length=2000)] | None = None
    author: Name = "propriétaire"


class ScriptRef(BaseModel):
    script_id: UUID
    author: Name = "propriétaire"


class AdaptIn(BaseModel):
    script_id: UUID
    content: Content
    title: Annotated[str, Field(max_length=300)] | None = None
    author: Name = "propriétaire"


@router.get("")
def scripts(request: Request) -> list[dict[str, Any]]:
    return _svc(request).scripts()


@router.post("", status_code=status.HTTP_201_CREATED)
def create(request: Request, body: ScriptIn) -> dict[str, str]:
    script_id = _call(
        _svc(request).create,
        title=body.title,
        language=body.language,
        content=body.content,
        author=body.author,
        document_ids=body.document_ids,
    )
    return {"script_id": str(script_id)}


@router.get("/{script_id}")
def script(request: Request, script_id: UUID) -> dict[str, Any]:
    result: dict[str, Any] = _call(_svc(request).script, script_id)
    return result


@router.post("/versions", status_code=status.HTTP_201_CREATED)
def add_version(request: Request, body: VersionIn) -> dict[str, Any]:
    result: dict[str, Any] = _call(
        _svc(request).add_version, body.script_id, body.content, author=body.author
    )
    return result


@router.post("/steps", status_code=status.HTTP_201_CREATED)
def move(request: Request, body: StepIn) -> dict[str, str]:
    _call(_svc(request).move, body.script_id, body.step, author=body.author, reason=body.reason)
    return {"status": "ok"}


@router.post("/evaluations", status_code=status.HTTP_201_CREATED)
def evaluate(request: Request, body: ScriptRef) -> dict[str, Any]:
    """Fact Checker + pré-notation sur 100 de la dernière version (gratuit)."""
    result: dict[str, Any] = _call(_svc(request).evaluate, body.script_id)
    return result


@router.post("/validations", status_code=status.HTTP_201_CREATED)
def validate(request: Request, body: ScriptRef) -> dict[str, str]:
    """Validation finale humaine : refusée en cas de veto factuel ou sous le seuil."""
    _call(_svc(request).validate, body.script_id, author=body.author)
    return {"status": "ok"}


@router.post("/adaptations", status_code=status.HTTP_201_CREATED)
def adapt(request: Request, body: AdaptIn) -> dict[str, str]:
    new_id = _call(
        _svc(request).adapt,
        body.script_id,
        content=body.content,
        title=body.title,
        author=body.author,
    )
    return {"script_id": str(new_id)}


# --- Phase 17 : niveaux, architectures, techniques ------------------------------------------

Level = Literal["DISCOVERY", "EXPLORATION", "EXPERTISE"]


class VariantIn(BaseModel):
    script_id: UUID
    level: Level
    content: Content
    title: Annotated[str, Field(max_length=300)] | None = None
    author: Name = "propriétaire"


class ArchitectureIn(BaseModel):
    subject: Annotated[str, Field(min_length=1, max_length=300)]
    facts: Annotated[list[Annotated[str, Field(max_length=2000)]], Field(max_length=50)] = []
    level: Level | None = None


@router.post("/variants", status_code=status.HTTP_201_CREATED)
def create_variant(request: Request, body: VariantIn) -> dict[str, str]:
    """Même sujet à un autre niveau ; même Fact Checker et même veto."""
    new_id = _call(
        _svc(request).variant,
        body.script_id,
        level=body.level,
        content=body.content,
        title=body.title,
        author=body.author,
    )
    return {"script_id": str(new_id)}


@router.post("/architectures")
def architectures(body: ArchitectureIn) -> list[dict[str, Any]]:
    """Plusieurs architectures narratives pour un sujet ; faits placés mot pour mot."""
    return propose(body.subject, body.facts, level=body.level)


@router.get("/techniques")
def list_techniques() -> list[dict[str, str]]:
    """Bibliothèque de principes narratifs (aucun contenu d'autres créateurs)."""
    return techniques()
