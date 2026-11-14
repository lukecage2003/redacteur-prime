"""Comic Intelligence — bibliothèque de comics (phase 2) ; vision et OCR en phase 3."""

from __future__ import annotations

from sqlalchemy import Engine

from primestone.comic.formats import DocumentFormat, Limits, RejectedDocumentError
from primestone.comic.library import (
    RENDER_STEP,
    VALIDATE_STEP,
    DocumentStatus,
    ImportItemResult,
    ImportOutcome,
    ImportResult,
    ImportSource,
    LibraryService,
    RenderProfile,
)
from primestone.config import Settings
from primestone.jobs import PostgresJobQueue
from primestone.storage import create_object_store

__all__ = [
    "RENDER_STEP",
    "VALIDATE_STEP",
    "DocumentFormat",
    "DocumentStatus",
    "ImportItemResult",
    "ImportOutcome",
    "ImportResult",
    "ImportSource",
    "LibraryService",
    "Limits",
    "RejectedDocumentError",
    "RenderProfile",
    "library_service_from_settings",
]


def library_service_from_settings(settings: Settings, engine: Engine) -> LibraryService:
    return LibraryService(
        engine,
        create_object_store(settings.storage_backend, settings.storage_local_root),
        PostgresJobQueue(engine),
        limits=Limits(
            max_file_bytes=settings.library_max_file_bytes,
            max_pages=settings.library_max_pages,
            max_image_pixels=settings.library_max_image_pixels,
        ),
        profile=RenderProfile(
            max_dimension=settings.render_max_dimension,
            webp_quality=settings.render_webp_quality,
        ),
    )
