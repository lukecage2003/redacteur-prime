"""Research et Theory Laboratory (phase 7) : théories prouvées et contestables, à coût nul."""

from sqlalchemy import Engine

from primestone.config import Settings
from primestone.forensic import forensic_service
from primestone.knowledge import knowledge_service_from_settings
from primestone.lab.scoring import METHOD, EvidenceInput, Score, score
from primestone.lab.service import EVIDENCE_LEVELS, ROLES, LabError, TheoryLab

__all__ = [
    "EVIDENCE_LEVELS",
    "METHOD",
    "ROLES",
    "EvidenceInput",
    "LabError",
    "Score",
    "TheoryLab",
    "lab_from_settings",
    "score",
]


def lab_from_settings(settings: Settings, engine: Engine) -> TheoryLab:
    return TheoryLab(
        engine, forensic_service(engine), knowledge_service_from_settings(settings, engine)
    )
