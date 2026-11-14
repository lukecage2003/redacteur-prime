"""Fournisseur de vision GRATUIT : modèle open source exécuté localement par Ollama.

Aucun coût d'API : le modèle tourne sur la machine de l'utilisateur (https://ollama.com).
Exemple : `ollama pull qwen2.5vl:7b`, puis `PRIMESTONE_VISION_PROVIDER=ollama`.
La sortie est contrainte par le même schéma JSON que l'adaptateur Claude, et validée.
"""

from __future__ import annotations

import base64
import io
import json
import time
from decimal import Decimal
from typing import Any

import httpx
from PIL import Image
from pydantic import ValidationError

from primestone.provenance import BoundingBox
from primestone.vision.models import TextRegion
from primestone.vision.providers import (
    _OUTPUT_SCHEMA,
    CLAUDE_SYSTEM_PROMPT,
    PageContext,
    VisionProviderError,
    VisionResult,
    _ClaudePage,
)

OLLAMA_PROMPT_VERSION = "vision.page_text@1.0.0+ollama"


class OllamaVisionProvider:
    name = "ollama"
    prompt_version = OLLAMA_PROMPT_VERSION

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5vl:7b",
        timeout_seconds: float = 600.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._transport = transport

    def estimate_cost(self, context: PageContext) -> Decimal:
        return Decimal("0")  # calcul local : aucun coût facturé

    @staticmethod
    def _png(image_webp: bytes) -> bytes:
        """Ollama attend du PNG/JPEG : conversion locale du rendu WebP."""
        buffer = io.BytesIO()
        Image.open(io.BytesIO(image_webp)).convert("RGB").save(buffer, format="PNG")
        return buffer.getvalue()

    async def analyze(self, context: PageContext) -> VisionResult:
        hints = {
            "reading_direction": context.direction.value,
            "language_hint": context.language_hint,
            "detected_panels": [{"index": p.index, **p.bbox.model_dump()} for p in context.panels],
        }
        body: dict[str, Any] = {
            "model": self.model,
            "stream": False,
            "format": _OUTPUT_SCHEMA,
            "options": {"temperature": 0},
            "messages": [
                {"role": "system", "content": CLAUDE_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": "Page hints:\n" + json.dumps(hints, ensure_ascii=False),
                    "images": [base64.b64encode(self._png(context.image_webp)).decode("ascii")],
                },
            ],
        }
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url, timeout=self._timeout, transport=self._transport
            ) as client:
                response = await client.post("/api/chat", json=body)
        except httpx.HTTPError as exc:
            raise VisionProviderError(
                f"Ollama injoignable sur {self._base_url} ({type(exc).__name__})"
            ) from exc
        if response.status_code == 404:
            raise VisionProviderError(
                f"modèle {self.model} absent : lancer `ollama pull {self.model}`", permanent=True
            )
        if response.status_code >= 400:
            raise VisionProviderError(f"Ollama HTTP {response.status_code}")
        payload = response.json()
        try:
            page = _ClaudePage.model_validate_json(payload["message"]["content"])
        except (KeyError, ValidationError) as exc:
            raise VisionProviderError("réponse JSON invalide du modèle local") from exc

        texts = []
        for item in page.texts:
            width, height = min(item.width, 1.0 - item.x), min(item.height, 1.0 - item.y)
            if width <= 0 or height <= 0:
                continue
            texts.append(
                TextRegion(
                    text=item.text,
                    kind=item.kind,
                    bbox=BoundingBox(x=item.x, y=item.y, width=width, height=height),
                    language=item.language,
                    confidence=item.confidence,
                    speaker=item.speaker,
                    speaker_confidence=item.speaker_confidence if item.speaker else None,
                )
            )
        return VisionResult(
            texts=texts,
            provider=self.name,
            model=str(payload.get("model", self.model)),
            prompt_version=self.prompt_version,
            cost_usd=Decimal("0"),
            input_tokens=int(payload.get("prompt_eval_count", 0)),
            output_tokens=int(payload.get("eval_count", 0)),
            latency_ms=(time.perf_counter() - started) * 1000,
        )
