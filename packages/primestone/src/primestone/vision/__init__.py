"""Comic Vision (phase 3) : cases, ordre de lecture, texte, locuteurs."""

from sqlalchemy import Engine

from primestone.config import Settings
from primestone.jobs import PostgresJobQueue
from primestone.storage import create_object_store
from primestone.vision.assign import assign_texts, iou
from primestone.vision.models import Panel, ReadingDirection, TextKind, TextRegion
from primestone.vision.panels import DETECTOR_VERSION, PanelConfig, detect_panels
from primestone.vision.providers import PageVisionProvider, create_vision_provider
from primestone.vision.service import VisionService

__all__ = [
    "DETECTOR_VERSION",
    "Panel",
    "PanelConfig",
    "ReadingDirection",
    "TextKind",
    "TextRegion",
    "assign_texts",
    "detect_panels",
    "iou",
    "vision_service_from_settings",
]


def vision_service_from_settings(settings: Settings, engine: Engine) -> VisionService:
    def factory(name: str) -> PageVisionProvider:
        return create_vision_provider(
            name,
            model=settings.vision_model,
            zero_cost=settings.zero_cost,
            ollama_url=settings.ollama_url,
        )

    return VisionService(
        engine,
        create_object_store(
            settings.storage_backend, settings.storage_local_root, gcs_bucket=settings.gcs_bucket
        ),
        PostgresJobQueue(engine),
        factory,
        zero_cost=settings.zero_cost,
    )
