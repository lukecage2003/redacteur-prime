"""Gestionnaires d'étapes de la Comic Library (traitements CPU exécutés hors boucle asyncio)."""

from __future__ import annotations

import asyncio
from typing import Any

from primestone.comic import RENDER_STEP, VALIDATE_STEP, LibraryService
from primestone_worker.handlers import HandlerRegistry


def register_library_handlers(registry: HandlerRegistry, service: LibraryService) -> None:
    async def validate(payload: dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(service.validate_document, payload)

    async def render(payload: dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(service.render_document_page, payload)

    registry.register(VALIDATE_STEP)(validate)
    registry.register(RENDER_STEP)(render)
