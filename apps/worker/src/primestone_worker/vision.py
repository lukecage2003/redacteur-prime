"""Gestionnaire d'étape Comic Vision."""

from __future__ import annotations

from typing import Any

from primestone.vision.service import ANALYZE_STEP, VisionService
from primestone_worker.handlers import HandlerRegistry


def register_vision_handlers(registry: HandlerRegistry, service: VisionService) -> None:
    async def analyze(payload: dict[str, Any]) -> dict[str, Any]:
        return await service.analyze_page(payload)

    registry.register(ANALYZE_STEP)(analyze)
