"""Routes Brand Intelligence et gouvernance (ADR-0027).

L'API est réservée au propriétaire (IAP) : ses décisions portent le rôle FOUNDER. Les agents
n'y passent jamais ; ils proposent via les services, côté serveur.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from primestone.governance import FOUNDER, GovernanceError, GovernanceService

router = APIRouter(prefix="/governance", tags=["governance"])
Short = Annotated[str, Field(min_length=1, max_length=500)]
Name = Annotated[str, Field(min_length=1, max_length=100)]
Action = Annotated[str, Field(pattern=r"^[A-Z_]{3,40}$")]


def _svc(request: Request) -> GovernanceService:
    service: GovernanceService = request.app.state.governance
    return service


def _fail(exc: GovernanceError) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))


class PillarIn(BaseModel):
    name: Short
    description: Annotated[str, Field(min_length=1, max_length=2000)]
    rules: dict[str, Any] = {}
    proposed_by: Name = "propriétaire"


class PolicyIn(BaseModel):
    action: Action
    requires_approval: bool
    note: Annotated[str, Field(max_length=2000)] | None = None
    proposed_by: Name = "propriétaire"


class DecideIn(BaseModel):
    decision_id: UUID
    decision: Literal["approve", "reject", "revert"]
    reason: Annotated[str, Field(max_length=2000)] = ""
    decided_by: Name = "propriétaire"


@router.get("/brands")
def brands(request: Request) -> list[dict[str, Any]]:
    return _svc(request).brands()


@router.get("/policies")
def policies(request: Request) -> list[dict[str, Any]]:
    return _svc(request).policies()


@router.post("/policies", status_code=status.HTTP_201_CREATED)
def propose_policy(request: Request, body: PolicyIn) -> dict[str, Any]:
    try:
        return _svc(request).propose_policy(
            body.action, body.requires_approval, note=body.note, proposed_by=body.proposed_by
        )
    except GovernanceError as exc:
        raise _fail(exc) from None


@router.get("/pillars")
def pillars(request: Request) -> list[dict[str, Any]]:
    return _svc(request).pillars()


@router.post("/pillars", status_code=status.HTTP_201_CREATED)
def propose_pillar(request: Request, body: PillarIn) -> dict[str, Any]:
    try:
        return _svc(request).propose_pillar(
            body.name, body.description, rules=body.rules, proposed_by=body.proposed_by
        )
    except GovernanceError as exc:
        raise _fail(exc) from None


@router.get("/decisions")
def decisions(
    request: Request,
    decision_status: Literal["PROPOSED", "APPROVED", "REJECTED", "SUPERSEDED", "REVERTED"]
    | None = None,
) -> list[dict[str, Any]]:
    return _svc(request).decisions(decision_status)


@router.post("/decide")
def decide(request: Request, body: DecideIn) -> dict[str, Any]:
    svc = _svc(request)
    try:
        if body.decision == "approve":
            return svc.approve(body.decision_id, decided_by=body.decided_by, role=FOUNDER)
        if body.decision == "reject":
            return svc.reject(
                body.decision_id, decided_by=body.decided_by, role=FOUNDER, reason=body.reason
            )
        return svc.revert(
            body.decision_id, decided_by=body.decided_by, role=FOUNDER, reason=body.reason
        )
    except GovernanceError as exc:
        raise _fail(exc) from None
