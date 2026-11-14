"""Gestionnaire d'étape : exécution durable d'une mission du Chief Editor."""

from __future__ import annotations

from typing import Any

from primestone.editorial import RUN_STEP, EditorialService
from primestone_worker.handlers import HandlerRegistry


def register_editorial_handlers(registry: HandlerRegistry, service: EditorialService) -> None:
    async def run(payload: dict[str, Any]) -> dict[str, Any]:
        return await service.run_mission(payload)

    registry.register(RUN_STEP)(run)
