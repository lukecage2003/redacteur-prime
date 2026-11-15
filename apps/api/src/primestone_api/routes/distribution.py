"""Routes Distribution et portefeuille (ADR-0030). Aucune route ne publie : la publication
est faite par le propriétaire sur la plateforme, puis déclarée ici."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from primestone.distribution import DistributionService

router = APIRouter(prefix="/distribution", tags=["distribution"])
Short = Annotated[str, Field(min_length=1, max_length=500)]
Name = Annotated[str, Field(min_length=1, max_length=100)]


def _svc(request: Request) -> DistributionService:
    service: DistributionService = request.app.state.distribution
    return service


def _call(fn: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return fn(*args, **kwargs)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None


class ChannelIn(BaseModel):
    platform: Name
    language: Literal["fr", "en"]
    handle: Name
    name: Name
    stats_authorization: Literal["NONE", "CSV_EXPORT", "OAUTH_READONLY"] = "NONE"


class ChannelStatusIn(BaseModel):
    channel_id: UUID
    status: Literal["ACTIVE", "PAUSED", "RETIRED"]


class PlanIn(BaseModel):
    channel_id: UUID
    title: Short
    script_id: UUID | None = None
    series_id: UUID | None = None
    format: Name | None = None
    scheduled_for: datetime | None = None
    proposed_by: Name = "propriétaire"


class DeclareIn(BaseModel):
    item_id: UUID
    url: Annotated[str, Field(pattern=r"^https://", max_length=1000)]
    external_id: Name
    declared_by: Name = "propriétaire"


class PortfolioIn(BaseModel):
    name: Name
    period_start: date
    period_end: date
    targets: dict[str, dict[str, Annotated[float, Field(ge=0, le=1)]]]
    created_by: Name = "propriétaire"


@router.get("/channels")
def channels(request: Request) -> list[dict[str, Any]]:
    return _svc(request).channels()


@router.post("/channels", status_code=status.HTTP_201_CREATED)
def add_channel(request: Request, body: ChannelIn) -> dict[str, str]:
    return {"channel_id": str(_call(_svc(request).add_channel, **body.model_dump()))}


@router.post("/channels/status")
def channel_status(request: Request, body: ChannelStatusIn) -> dict[str, str]:
    _call(_svc(request).set_channel_status, body.channel_id, body.status)
    return {"status": body.status}


@router.get("/channels/performance")
def channel_performance(request: Request) -> list[dict[str, Any]]:
    return _svc(request).channel_performance()


@router.get("/plan")
def plan(
    request: Request, start: date | None = None, end: date | None = None
) -> list[dict[str, Any]]:
    return _svc(request).plan(start=start, end=end)


@router.post("/plan", status_code=status.HTTP_201_CREATED)
def propose(request: Request, body: PlanIn) -> dict[str, Any]:
    result: dict[str, Any] = _call(_svc(request).propose, **body.model_dump())
    return result


@router.post("/plan/declarations")
def declare(request: Request, body: DeclareIn) -> dict[str, str]:
    content_id = _call(
        _svc(request).declare_published,
        body.item_id,
        url=body.url,
        external_id=body.external_id,
        declared_by=body.declared_by,
    )
    return {"content_id": str(content_id), "status": "PUBLISHED"}


@router.get("/portfolios")
def portfolios(request: Request) -> list[dict[str, Any]]:
    return _svc(request).portfolios()


@router.post("/portfolios", status_code=status.HTTP_201_CREATED)
def create_portfolio(request: Request, body: PortfolioIn) -> dict[str, str]:
    data = body.model_dump()
    name = data.pop("name")
    return {"portfolio_id": str(_call(_svc(request).create_portfolio, name, **data))}


@router.get("/portfolios/{portfolio_id}")
def portfolio(request: Request, portfolio_id: UUID) -> dict[str, Any]:
    result: dict[str, Any] = _call(_svc(request).portfolio, portfolio_id)
    return result
