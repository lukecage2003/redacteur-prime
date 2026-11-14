"""Fournisseur de texte GRATUIT : modèle open source local via Ollama (coût facturé nul)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import httpx

from primestone.ai_gateway.base import CompletionRequest, CompletionResult, Usage


class OllamaLLMProvider:
    name = "ollama"

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5:7b",
        timeout_seconds: float = 600.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._transport = transport

    def estimate_cost(self, request: CompletionRequest) -> Decimal:
        return Decimal("0")

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        messages: list[dict[str, Any]] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages += [{"role": m.role, "content": m.content} for m in request.messages]
        body = {
            "model": request.model or self.model,
            "stream": False,
            "messages": messages,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_output_tokens,
            },
        }
        async with httpx.AsyncClient(
            base_url=self._base_url, timeout=self._timeout, transport=self._transport
        ) as client:
            response = await client.post("/api/chat", json=body)
        response.raise_for_status()
        payload = response.json()
        return CompletionResult(
            text=payload["message"]["content"],
            provider=self.name,
            model=str(payload.get("model", self.model)),
            usage=Usage(
                input_tokens=int(payload.get("prompt_eval_count", 0)),
                output_tokens=int(payload.get("eval_count", 0)),
                cost_usd=Decimal("0"),
            ),
        )
