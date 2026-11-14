"""Routes Market Intelligence (coût nul). Écritures sur URLs fixes, valeurs dans le corps."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from primestone.market import MarketError, MarketService

router = APIRouter(prefix="/market", tags=["market"])

Short = Annotated[str, Field(min_length=1, max_length=200)]
Name = Annotated[str, Field(min_length=1, max_length=100)]


def _market(request: Request) -> MarketService:
    market: MarketService = request.app.state.market
    return market


def _call(fn: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return fn(*args, **kwargs)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from None
    except MarketError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None


class SourceIn(BaseModel):
    key: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,62}$")]
    name: Short
    kind: Literal["YOUTUBE_API", "RSS", "MANUAL"]
    access: Annotated[str, Field(min_length=1, max_length=1000)]
    quota: Annotated[str, Field(min_length=1, max_length=1000)]
    terms_url: Annotated[str, Field(min_length=1, max_length=500)]
    language: Literal["fr", "en"] | None = None
    url: Annotated[str, Field(max_length=500)] | None = None


class VerifyIn(BaseModel):
    key: Annotated[str, Field(max_length=63)]
    author: Name = "propriétaire"


class RecordIn(BaseModel):
    """Compteurs publics uniquement : un champ inconnu (ctr, retention…) est refusé (422)."""

    model_config = {"extra": "forbid"}
    platform: Annotated[str, Field(min_length=1, max_length=50)]
    external_id: Annotated[str, Field(min_length=1, max_length=500)]
    title: Annotated[str, Field(min_length=1, max_length=1000)]
    language: Literal["fr", "en"]
    observed_at: Annotated[str, Field(max_length=40)]
    published_at: Annotated[str, Field(max_length=40)] | None = None
    url: Annotated[str, Field(max_length=500)] | None = None
    channel: Annotated[str, Field(max_length=300)] | None = None
    description: Annotated[str, Field(max_length=5000)] | None = None
    views: Annotated[int, Field(ge=0)] | None = None
    likes: Annotated[int, Field(ge=0)] | None = None
    comments: Annotated[int, Field(ge=0)] | None = None


class ImportIn(BaseModel):
    model_config = {"extra": "forbid"}
    source: Annotated[str, Field(max_length=63)]
    records: Annotated[list[RecordIn], Field(min_length=1, max_length=5000)]
    author: Name = "propriétaire"


class CollectIn(BaseModel):
    source: Annotated[str, Field(max_length=63)]
    query: Annotated[str, Field(max_length=200)] | None = None
    language: Literal["fr", "en"] = "en"
    max_results: Annotated[int, Field(ge=1, le=50)] = 25


class TopicIn(BaseModel):
    name: Short
    keywords_fr: Annotated[list[Short], Field(max_length=20)] = []
    keywords_en: Annotated[list[Short], Field(max_length=20)] = []
    author: Name = "propriétaire"


@router.get("/sources")
def sources(request: Request) -> list[dict[str, Any]]:
    return _market(request).sources()


@router.post("/sources", status_code=status.HTTP_201_CREATED)
def register_source(request: Request, body: SourceIn) -> dict[str, str]:
    source_id = _call(
        _market(request).register_source,
        key=body.key,
        name=body.name,
        kind=body.kind,
        access=body.access,
        quota=body.quota,
        terms_url=body.terms_url,
        language=body.language,
        config={"url": body.url} if body.url else {},
    )
    return {"source_id": str(source_id)}


@router.post("/sources/verifications", status_code=status.HTTP_201_CREATED)
def verify_source(request: Request, body: VerifyIn) -> dict[str, str]:
    """Validation humaine de la fiche : aucune collecte avant."""
    _call(_market(request).verify_source, body.key, author=body.author)
    return {"status": "ok"}


@router.post("/imports", status_code=status.HTTP_201_CREATED)
def import_records(request: Request, body: ImportIn) -> dict[str, Any]:
    result: dict[str, Any] = _call(
        _market(request).import_records,
        body.source,
        [r.model_dump(exclude_none=True) for r in body.records],
        author=body.author,
    )
    return result


@router.post("/collections", status_code=status.HTTP_201_CREATED)
def collect(request: Request, body: CollectIn) -> dict[str, Any]:
    """Collecte immédiate : RSS, ou recherche YouTube (quota gratuit contrôlé)."""
    market = _market(request)
    kinds = {s["key"]: s["kind"] for s in market.sources()}
    if body.source not in kinds:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"source inconnue : {body.source}")
    if kinds[body.source] == "RSS":
        result: dict[str, Any] = _call(market.collect_rss, body.source)
    elif kinds[body.source] == "YOUTUBE_API":
        if not body.query:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "requête obligatoire")
        result = _call(
            market.collect_youtube,
            body.source,
            body.query,
            language=body.language,
            max_results=body.max_results,
        )
    else:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "source manuelle : /imports")
    return result


@router.get("/collections")
def collections(request: Request) -> list[dict[str, Any]]:
    return _market(request).collections()


@router.get("/topics")
def topics(request: Request) -> list[dict[str, Any]]:
    return _market(request).topics()


@router.post("/topics", status_code=status.HTTP_201_CREATED)
def add_topic(request: Request, body: TopicIn) -> dict[str, str]:
    topic_id = _call(
        _market(request).add_topic,
        body.name,
        keywords_fr=body.keywords_fr,
        keywords_en=body.keywords_en,
        author=body.author,
    )
    return {"topic_id": str(topic_id)}


@router.get("/analysis")
def analysis(
    request: Request,
    window_days: Annotated[int, Query(ge=1, le=3650)] = 90,
    min_items: Annotated[int, Query(ge=1, le=1000)] = 5,
) -> dict[str, Any]:
    return _market(request).analysis(window_days=window_days, min_items=min_items)
