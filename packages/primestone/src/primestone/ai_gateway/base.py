"""Contrats de la passerelle IA."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class BudgetExceededError(RuntimeError):
    """Levée avant un appel qui ferait dépasser le budget alloué."""


class Message(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: Literal["user", "assistant"]
    content: str


class CompletionRequest(BaseModel):
    """Requête de génération. `prompt_id`/`prompt_version` référencent `prompts/` (versionné)."""

    model_config = ConfigDict(frozen=True)

    prompt_id: Annotated[str, Field(min_length=1)]
    prompt_version: Annotated[str, Field(min_length=1)]
    system: str | None = None
    messages: Annotated[list[Message], Field(min_length=1)]
    max_output_tokens: Annotated[int, Field(gt=0)] = 1024
    temperature: Annotated[float, Field(ge=0.0, le=2.0)] = 0.2
    model: str | None = None  # None = modèle par défaut du fournisseur


class Usage(BaseModel):
    model_config = ConfigDict(frozen=True)

    input_tokens: Annotated[int, Field(ge=0)]
    output_tokens: Annotated[int, Field(ge=0)]
    cost_usd: Annotated[Decimal, Field(ge=0)]


class CompletionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    provider: str
    model: str
    usage: Usage


class CallRecord(BaseModel):
    """Trace d'un appel, destinée à la table `agent_run` (Phase 6)."""

    model_config = ConfigDict(frozen=True)

    provider: str
    model: str
    prompt_id: str
    prompt_version: str
    usage: Usage | None
    latency_ms: float
    started_at: datetime
    error: str | None = None


@runtime_checkable
class LLMProvider(Protocol):
    """Adaptateur d'un fournisseur de modèles de langage."""

    name: str

    def estimate_cost(self, request: CompletionRequest) -> Decimal:
        """Coût maximal estimé de la requête (sert au contrôle de budget avant l'appel)."""
        ...

    async def complete(self, request: CompletionRequest) -> CompletionResult: ...
