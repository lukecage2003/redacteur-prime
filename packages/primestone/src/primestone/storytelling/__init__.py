"""Maximum Storytelling (phase 10) : scripts en 13 étapes, pré-notation sur 100, veto
factuel, adaptation FR/EN, validation humaine — coût nul."""

from sqlalchemy import Engine

from primestone.forensic import forensic_service
from primestone.storytelling.analysis import (
    METHOD,
    WEIGHTS,
    Section,
    score,
    sections,
    work_citations,
)
from primestone.storytelling.architectures import ARCHITECTURES, propose, techniques
from primestone.storytelling.levels import LEVELS
from primestone.storytelling.retention import motion_intents
from primestone.storytelling.service import (
    PASS_MARK,
    ScriptError,
    StorytellingService,
    read_script_file,
)

__all__ = [
    "ARCHITECTURES",
    "LEVELS",
    "METHOD",
    "PASS_MARK",
    "WEIGHTS",
    "ScriptError",
    "Section",
    "StorytellingService",
    "motion_intents",
    "propose",
    "read_script_file",
    "score",
    "sections",
    "storytelling_service",
    "techniques",
    "work_citations",
]


def storytelling_service(engine: Engine) -> StorytellingService:
    return StorytellingService(engine, forensic_service(engine))
