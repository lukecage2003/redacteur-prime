"""Registre des gestionnaires d'étapes. Chaque module métier y enregistre les siens."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from primestone.jobs import PermanentError

__all__ = ["Handler", "HandlerRegistry", "PermanentError", "registry"]

Handler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


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

    def names(self) -> list[str]:
        return sorted(self._handlers)


def default_registry() -> HandlerRegistry:
    """Registre de base (diagnostic). Les modules métier y ajoutent leurs gestionnaires."""
    reg = HandlerRegistry()
    reg.register("system.ping")(ping)
    return reg


async def ping(payload: dict[str, Any]) -> dict[str, Any]:
    """Étape de diagnostic : vérifie la chaîne file → worker → résultat."""
    return {"pong": True, "echo": payload.get("echo")}


registry = default_registry()
