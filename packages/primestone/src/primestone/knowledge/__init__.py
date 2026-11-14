"""Knowledge Intelligence (phase 5) : entités, relations prouvées, corrections, graphe,
recherche hybride — sans aucun coût."""

from sqlalchemy import Engine

from primestone.config import Settings
from primestone.forensic import forensic_service
from primestone.knowledge.embeddings import Embedder, HashingEmbedder, OllamaEmbedder
from primestone.knowledge.search import hybrid_search
from primestone.knowledge.service import KnowledgeError, KnowledgeService, ManualEvidence

__all__ = [
    "Embedder",
    "HashingEmbedder",
    "KnowledgeError",
    "KnowledgeService",
    "ManualEvidence",
    "OllamaEmbedder",
    "hybrid_search",
    "knowledge_service_from_settings",
]


def knowledge_service_from_settings(settings: Settings, engine: Engine) -> KnowledgeService:
    embedder: Embedder
    if settings.embedder == "ollama":
        embedder = OllamaEmbedder(base_url=settings.ollama_url, model=settings.embedding_model)
    else:
        embedder = HashingEmbedder()
    return KnowledgeService(engine, forensic_service(engine), embedder)
