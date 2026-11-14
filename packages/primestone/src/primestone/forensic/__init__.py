"""Forensic Intelligence (phase 4) : observations prouvées, sans aucun coût."""

from sqlalchemy import Engine

from primestone.forensic.extract import (
    EXTRACTOR_VERSION,
    Evidence,
    EvidenceRole,
    ForensicObservation,
    ObservationKind,
    TextRow,
    extract,
    fold,
)
from primestone.forensic.service import ForensicService
from primestone.jobs import PostgresJobQueue

__all__ = [
    "EXTRACTOR_VERSION",
    "Evidence",
    "EvidenceRole",
    "ForensicObservation",
    "ForensicService",
    "ObservationKind",
    "TextRow",
    "extract",
    "fold",
    "forensic_service",
]


def forensic_service(engine: Engine) -> ForensicService:
    return ForensicService(engine, PostgresJobQueue(engine))
