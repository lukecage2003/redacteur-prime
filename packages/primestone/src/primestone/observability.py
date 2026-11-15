"""Journalisation JSON structurée et identifiant de requête (traçage simple, coût nul).

Format compatible Cloud Logging (`severity`, `message`, `logging.googleapis.com/trace`
facultatif). Les secrets ne sont jamais journalisés : seuls les champs explicitement passés
dans `extra={"fields": {...}}` sont ajoutés, après filtrage des clés sensibles.
"""

from __future__ import annotations

import contextvars
import json
import logging
import re
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "primestone_request_id", default=None
)
_SENSITIVE = re.compile(r"(key|token|secret|password|authorization|cookie)", re.IGNORECASE)
_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "severity": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        rid = request_id.get()
        if rid:
            payload["request_id"] = rid
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            payload.update(
                {k: ("[masqué]" if _SENSITIVE.search(k) else v) for k, v in fields.items()}
            )
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO", fmt: str = "text") -> None:
    """Configure la racine : texte lisible en développement, JSON ailleurs."""
    handler = logging.StreamHandler()
    if fmt == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)


Scope = dict[str, Any]
Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]


class RequestIdMiddleware:
    """Propage `X-Request-ID` (fourni s'il est sûr, sinon généré) dans les journaux et la
    réponse ; journalise méthode, chemin, statut et durée (jamais le corps ni la requête)."""

    def __init__(self, app: Callable[[Scope, Receive, Send], Awaitable[None]]) -> None:
        self.app = app
        self.log = logging.getLogger("primestone.api.access")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        incoming = dict(scope.get("headers") or []).get(b"x-request-id", b"").decode("latin-1")
        rid = incoming if _SAFE_ID.match(incoming) else uuid.uuid4().hex
        token = request_id.set(rid)
        started = datetime.now(UTC)
        status: dict[str, int] = {}

        async def send_with_id(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                message["headers"] = [*message.get("headers", []), (b"x-request-id", rid.encode())]
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            elapsed = (datetime.now(UTC) - started).total_seconds() * 1000
            self.log.info(
                "%s %s %s",
                scope.get("method", "WS"),
                scope.get("path"),
                status.get("code", "-"),
                extra={
                    "fields": {
                        "method": scope.get("method", "WS"),
                        "path": scope.get("path"),
                        "status": status.get("code"),
                        "duration_ms": round(elapsed, 1),
                    }
                },
            )
            request_id.reset(token)
