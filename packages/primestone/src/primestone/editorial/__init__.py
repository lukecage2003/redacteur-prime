"""Editorial Intelligence (phase 6) : Chief Editor et agents spécialisés, à coût nul."""

from collections.abc import Callable
from typing import TYPE_CHECKING

from sqlalchemy import Engine

from primestone.ai_gateway import LLMProvider, default_registry
from primestone.config import Settings
from primestone.editorial.agents import AGENTS, MISSION_TYPES, MissionContext, plan
from primestone.editorial.factcheck import Corpus, FactCheckReport, Verdict, check_text
from primestone.editorial.service import RUN_STEP, EditorialError, EditorialService
from primestone.forensic import ForensicService, forensic_service
from primestone.jobs import PostgresJobQueue
from primestone.knowledge import knowledge_service_from_settings
from primestone.lab import TheoryLab

if TYPE_CHECKING:
    from primestone.storytelling import StorytellingService
from primestone.market import market_service_from_settings
from primestone.performance import PerformanceService

__all__ = [
    "AGENTS",
    "MISSION_TYPES",
    "RUN_STEP",
    "Corpus",
    "EditorialError",
    "EditorialService",
    "FactCheckReport",
    "MissionContext",
    "Verdict",
    "check_text",
    "editorial_service_from_settings",
    "plan",
]


def _storytelling(engine: Engine, forensic: ForensicService) -> "StorytellingService":
    from primestone.storytelling import StorytellingService  # import circulaire évité

    return StorytellingService(engine, forensic)


def editorial_service_from_settings(settings: Settings, engine: Engine) -> EditorialService:
    writer: Callable[[], LLMProvider] | None = None
    if settings.editorial_writer != "none":
        registry = default_registry(
            ollama_url=settings.ollama_url, ollama_model=settings.ollama_text_model
        )
        name = settings.editorial_writer

        def writer() -> LLMProvider:
            return registry.create(name)

    forensic = forensic_service(engine)
    knowledge = knowledge_service_from_settings(settings, engine)
    return EditorialService(
        engine,
        forensic,
        knowledge,
        PostgresJobQueue(engine),
        writer,
        lab=TheoryLab(engine, forensic, knowledge),
        market=market_service_from_settings(settings, engine),
        storytelling=_storytelling(engine, forensic),
        performance=PerformanceService(engine),
    )
