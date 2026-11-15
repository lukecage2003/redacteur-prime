"""Creative Intelligence (phase 18) : packaging honnête, charte de marque versionnée, séries
et franchises — coût nul (modèle local facultatif pour proposer d'autres titres)."""

from decimal import Decimal

from sqlalchemy import Engine

from primestone.ai_gateway import AIGateway, CompletionRequest, Message, default_registry
from primestone.config import Settings
from primestone.creative.brand import DEFAULT_CHARTER, check_text, check_thumbnail
from primestone.creative.packaging import METHOD, build
from primestone.creative.service import CreativeError, CreativeService, TitleWriter

__all__ = [
    "DEFAULT_CHARTER",
    "METHOD",
    "CreativeError",
    "CreativeService",
    "build",
    "check_text",
    "check_thumbnail",
    "creative_service_from_settings",
]


def creative_service_from_settings(settings: Settings, engine: Engine) -> CreativeService:
    writer: TitleWriter | None = None
    if settings.editorial_writer != "none":
        provider = default_registry(
            ollama_url=settings.ollama_url, ollama_model=settings.ollama_text_model
        ).create(settings.editorial_writer)
        gateway = AIGateway(provider, Decimal("0"), zero_cost=True)

        async def writer_fn(subject: str, script: str) -> list[str]:
            result = await gateway.complete(
                CompletionRequest(
                    prompt_id="creative.titles",
                    prompt_version="1.0.0",
                    system=(
                        "Propose 10 titres YouTube honnêtes, un par ligne, sans guillemets, "
                        "fidèles au script, sans sensationnalisme ni promesse non tenue."
                    ),
                    messages=[
                        Message(role="user", content=f"Sujet : {subject}\n\n{script[:6000]}")
                    ],
                    max_output_tokens=400,
                    temperature=0.7,
                )
            )
            return [line.strip(" -•\t") for line in result.text.splitlines() if line.strip()]

        writer = writer_fn
    return CreativeService(engine, writer)
