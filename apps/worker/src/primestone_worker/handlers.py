"""Registre des gestionnaires d'étapes. Chaque module métier y enregistre les siens."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

Handler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class PermanentError(Exception):
    """Erreur non réessayable (entrée invalide, gestionnaire inconnu…) : étape marquée DEAD."""


class HandlerRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, Handler] = {}

    def register(self, name: str) -> Callable[[Handler], Handler]:
        def decorator(fn: Handler) -> Handler:
            if name in self._handlers:
                raise ValueError(f"gestionnaire déjà enregistré : {name}")
            self._handlers[name] = fn
            return fn

        return decorator

    def get(self, name: str) -> Handler:
        try:
            return self._handlers[name]
        except KeyError:
            raise PermanentError(f"aucun gestionnaire pour l'étape « {name} »") from None


registry = HandlerRegistry()


@registry.register("system.ping")
async def ping(payload: dict[str, Any]) -> dict[str, Any]:
    """Étape de diagnostic : vérifie la chaîne file → worker → résultat."""
    return {"pong": True, "echo": payload.get("echo")}
