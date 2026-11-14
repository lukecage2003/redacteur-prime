"""Fournisseur simulé, déterministe et gratuit : le seul autorisé en CI."""

from __future__ import annotations

import hashlib
from decimal import Decimal

from primestone.ai_gateway.base import CompletionRequest, CompletionResult, Usage


class FakeLLMProvider:
    name = "fake"
    model = "fake-deterministic-1"

    def __init__(
        self,
        responses: dict[str, str] | None = None,
        cost_per_call_usd: Decimal = Decimal("0"),
        fail_with: Exception | None = None,
    ) -> None:
        self._responses = responses or {}
        self._cost = cost_per_call_usd
        self._fail_with = fail_with
        self.calls: list[CompletionRequest] = []

    def estimate_cost(self, request: CompletionRequest) -> Decimal:
        return self._cost

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        self.calls.append(request)
        if self._fail_with is not None:
            raise self._fail_with
        last = request.messages[-1].content
        text = self._responses.get(request.prompt_id)
        if text is None:
            digest = hashlib.sha256(f"{request.prompt_id}:{last}".encode()).hexdigest()[:12]
            text = f"[fake:{request.prompt_id}@{request.prompt_version}:{digest}]"
        return CompletionResult(
            text=text,
            provider=self.name,
            model=request.model or self.model,
            usage=Usage(
                input_tokens=sum(len(m.content.split()) for m in request.messages),
                output_tokens=len(text.split()),
                cost_usd=self._cost,
            ),
        )
