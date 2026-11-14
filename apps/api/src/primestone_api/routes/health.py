from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import Engine, text

from primestone import __version__

router = APIRouter(tags=["health"])


class Health(BaseModel):
    status: Literal["ok", "unavailable"]
    version: str
    environment: str
    checks: dict[str, str] = {}


@router.get("/health", response_model=Health)
def liveness(request: Request) -> Health:
    """Le processus répond (sonde de vivacité Cloud Run). Ne touche pas aux dépendances."""
    return Health(
        status="ok", version=__version__, environment=request.app.state.settings.environment
    )


@router.get(
    "/health/ready",
    response_model=Health,
    responses={503: {"model": Health}},
)
def readiness(request: Request, response: Response) -> Health:
    """Prêt à servir : la base de données répond."""
    engine: Engine = request.app.state.engine
    checks: dict[str, str] = {}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {type(exc).__name__}"
    healthy = all(v == "ok" for v in checks.values())
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return Health(
        status="ok" if healthy else "unavailable",
        version=__version__,
        environment=request.app.state.settings.environment,
        checks=checks,
    )
