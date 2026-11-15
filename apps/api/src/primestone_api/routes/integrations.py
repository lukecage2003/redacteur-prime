"""API d'intégration (lecture seule, contrats versionnés) pour les outils Primestone.

- Panel Explorer : une page = cases dans l'ordre de lecture + textes de la transcription servie.
- Motion Studio : un script VALIDÉ = sections horodatées, texte, références ; seul un script
  validé (sans veto factuel) est exposé, jamais un brouillon.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status

from primestone.storytelling import StorytellingService, motion_intents, sections
from primestone.vision.service import VisionService

router = APIRouter(prefix="/integrations", tags=["integrations"])
CONTRACT = "1.1"  # 1.1 : intentions narratives et moments visuels (compatible 1.0)


@router.get("/panel-explorer/documents/{document_id}/pages/{number}")
def panel_explorer_page(request: Request, document_id: UUID, number: int) -> dict[str, Any]:
    vision: VisionService = request.app.state.vision
    analysis = vision.latest_analysis(document_id, number)
    panels = vision.page_panels(document_id, number)
    if panels is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "page non rendue")
    return {
        "contract": CONTRACT,
        "document_id": str(document_id),
        "page": number,
        "image_url": f"/api/v1/library/documents/{document_id}/pages/{number}/image",
        "panels": panels,
        "texts": (analysis or {}).get("texts", []),
        "transcribed": analysis is not None,
        "source": (analysis or {}).get("provider"),
    }


@router.get("/motion-studio/scripts/{script_id}")
def motion_studio_script(request: Request, script_id: UUID) -> dict[str, Any]:
    stories: StorytellingService = request.app.state.storytelling
    try:
        script = stories.script(script_id)
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "script introuvable") from None
    if script["status"] != "VALIDATED":
        raise HTTPException(status.HTTP_409_CONFLICT, "script non validé : non exposé")
    version = script["versions"][-1]
    score = script["scores"][-1]
    return {
        "contract": CONTRACT,
        "script_id": script["id"],
        "title": script["title"],
        "language": script["language"],
        "version": version["number"],
        "score": score["total"],
        "sections": [
            {"title": s.title, "start_seconds": s.start_seconds, "text": s.text}
            for s in sections(version["content"])
        ],
        "works": score["analysis"]["works"],
        "intents": motion_intents(score["analysis"]["retention"])
        if "retention" in score["analysis"]
        else [],
        "adapted_from": script["adapted_from"],
        "adaptations": script["adaptations"],
    }
