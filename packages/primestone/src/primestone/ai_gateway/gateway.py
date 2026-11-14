"""Registre des fournisseurs et passerelle avec budget et traçabilité."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

from primestone.ai_gateway.base import (
    BudgetExceededError,
    CallRecord,
    CompletionRequest,
    CompletionResult,
    LLMProvider,
)
from primestone.ai_gateway.fake import FakeLLMProvider

ProviderFactory = Callable[[], LLMProvider]


class ProviderRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, ProviderFactory] = {}

    def register(self, name: str, factory: ProviderFactory) -> None:
        if name in self._factories:
            raise ValueError(f"fournisseur déjà enregistré : {name}")
        self._factories[name] = factory

    def create(self, name: str) -> LLMProvider:
        try:
            factory = self._factories[name]
        except KeyError:
            known = ", ".join(sorted(self._factories)) or "aucun"
            raise LookupError(f"fournisseur inconnu : {name} (connus : {known})") from None
        return factory()

    def names(self) -> list[str]:
        return sorted(self._factories)


def default_registry() -> ProviderRegistry:
    """Registre par défaut. Les adaptateurs réels seront ajoutés après benchmark (Phase 3)."""
    registry = ProviderRegistry()
    registry.register("fake", FakeLLMProvider)
    return registry


class AIGateway:
    """Point d'entrée unique du code métier vers les modèles.

    - contrôle le budget *avant* chaque appel (estimation) et *après* (coût réel) ;
    - enregistre chaque appel, réussi ou non, dans `records`.
    """

    def __init__(self, provider: LLMProvider, budget_usd: Decimal) -> None:
        if budget_usd < 0:
            raise ValueError("le budget doit être positif")
        self._provider = provider
        self._budget = budget_usd
        self._spent = Decimal("0")
        self.records: list[CallRecord] = []

    @property
    def spent_usd(self) -> Decimal:
        return self._spent

    @property
    def remaining_usd(self) -> Decimal:
        return self._budget - self._spent

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        estimate = self._provider.estimate_cost(request)
        if self._spent + estimate > self._budget:
            raise BudgetExceededError(
                f"appel refusé : estimé {estimate} USD, restant {self.remaining_usd} USD"
            )
        started_at = datetime.now(UTC)
        t0 = time.perf_counter()
        try:
            result = await self._provider.complete(request)
        except Exception as exc:
            self.records.append(
                CallRecord(
                    provider=self._provider.name,
                    model=request.model or "default",
                    prompt_id=request.prompt_id,
                    prompt_version=request.prompt_version,
                    usage=None,
                    latency_ms=(time.perf_counter() - t0) * 1000,
                    started_at=started_at,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
            raise
        self._spent += result.usage.cost_usd
        self.records.append(
            CallRecord(
                provider=result.provider,
                model=result.model,
                prompt_id=request.prompt_id,
                prompt_version=request.prompt_version,
                usage=result.usage,
                latency_ms=(time.perf_counter() - t0) * 1000,
                started_at=started_at,
            )
        )
        return result
