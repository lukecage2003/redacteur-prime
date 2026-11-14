"""Passerelle IA indépendante des fournisseurs (ADR-0005).

Le code métier ne parle qu'à `AIGateway`. Chaque appel est tracé (fournisseur, modèle,
version de prompt, jetons, coût, latence) et soumis à un budget. Les fournisseurs réels
sont des adaptateurs ajoutés au registre ; la CI n'utilise que `FakeLLMProvider`.
"""

from primestone.ai_gateway.base import (
    BudgetExceededError,
    CallRecord,
    CompletionRequest,
    CompletionResult,
    LLMProvider,
    Message,
    Usage,
)
from primestone.ai_gateway.fake import FakeLLMProvider
from primestone.ai_gateway.gateway import AIGateway, ProviderRegistry, default_registry

__all__ = [
    "AIGateway",
    "BudgetExceededError",
    "CallRecord",
    "CompletionRequest",
    "CompletionResult",
    "FakeLLMProvider",
    "LLMProvider",
    "Message",
    "ProviderRegistry",
    "Usage",
    "default_registry",
]
