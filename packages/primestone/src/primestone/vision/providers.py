"""Fournisseurs d'analyse visuelle d'une page (texte, type de texte, locuteurs).

Interface commune `PageVisionProvider` (ADR-0005 : indépendance des fournisseurs) :
- `FakeVisionProvider` : déterministe, gratuit — seul autorisé en CI ;
- `ClaudeVisionProvider` : Claude (SDK officiel `anthropic`), sortie JSON contrainte par schéma.

Le coût est estimé AVANT l'appel (contrôle de budget) puis mesuré à partir de l'usage réel.
"""

from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field, ValidationError

from primestone.provenance import BoundingBox
from primestone.vision.models import Panel, ReadingDirection, TextKind, TextRegion


class VisionProviderError(RuntimeError):
    """Échec du fournisseur (réessayable, sauf `permanent`)."""

    def __init__(self, message: str, *, permanent: bool = False) -> None:
        super().__init__(message)
        self.permanent = permanent


@dataclass(frozen=True)
class PageContext:
    """Ce que le fournisseur reçoit pour une page."""

    image_webp: bytes
    width: int
    height: int
    panels: list[Panel]  # issues du détecteur local, pour guider l'analyse
    direction: ReadingDirection = ReadingDirection.LTR
    language_hint: str | None = None  # "fr", "en" ou None
    known_characters: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class VisionResult:
    texts: list[TextRegion]
    provider: str
    model: str
    prompt_version: str
    cost_usd: Decimal
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0


@runtime_checkable
class PageVisionProvider(Protocol):
    name: str
    model: str
    prompt_version: str

    def estimate_cost(self, context: PageContext) -> Decimal: ...

    async def analyze(self, context: PageContext) -> VisionResult: ...


# --- Fournisseur simulé -------------------------------------------------------------------


class FakeVisionProvider:
    """Renvoie des textes scénarisés (par numéro de page via `script`) ou aucun texte."""

    name = "fake"
    model = "fake-vision-1"
    prompt_version = "fake-1"

    def __init__(
        self,
        script: dict[int, list[TextRegion]] | None = None,
        cost_per_page_usd: Decimal = Decimal("0"),
        fail_with: Exception | None = None,
    ) -> None:
        self._script = script or {}
        self._cost = cost_per_page_usd
        self._fail_with = fail_with
        self.calls: list[PageContext] = []

    def estimate_cost(self, context: PageContext) -> Decimal:
        return self._cost

    async def analyze(self, context: PageContext) -> VisionResult:
        self.calls.append(context)
        if self._fail_with is not None:
            raise self._fail_with
        page_number = len(self.calls)
        texts = list(self._script.get(page_number, self._script.get(0, [])))
        return VisionResult(
            texts=texts,
            provider=self.name,
            model=self.model,
            prompt_version=self.prompt_version,
            cost_usd=self._cost,
        )


# --- Claude -------------------------------------------------------------------------------

CLAUDE_PROMPT_VERSION = "vision.page_text@1.0.0"

CLAUDE_SYSTEM_PROMPT = """\
You are the transcription stage of a forensic comics-analysis pipeline. Your output becomes \
documentary evidence, so exactness matters more than completeness.

For the comic page image, return every piece of lettering:
- text: transcribe exactly as lettered (keep the original language, punctuation, ellipses, \
emphasis words). Never translate, summarise or correct. Join lines of one balloon with spaces.
- kind: DIALOGUE (speech balloon), THOUGHT (thought balloon), NARRATION (caption box / \
narrator), SFX (sound effect), CAPTION (title, credits, editor note), OTHER (signs, screens, \
text drawn in the scene).
- bbox: the region of the lettering, normalised to the page (x, y = top-left corner; width, \
height; all between 0 and 1).
- language: ISO 639-1 code of the text.
- confidence: your confidence in the transcription (0-1). Lower it for unclear lettering.
- speaker: only for DIALOGUE/THOUGHT, the character name if the page itself makes it \
identifiable (named in the text, unambiguous tail to a recognisable character, or one of the \
known characters). Otherwise null. Never guess from outside knowledge of the series.
- speaker_confidence: 0-1, null when speaker is null.

Detected panels are given as hints (normalised boxes in reading order); they may be imperfect. \
Do not invent text that is not visible. If the page has no lettering, return an empty list."""


class _ClaudeText(BaseModel):
    text: str = Field(min_length=1)
    kind: TextKind
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)
    language: str | None
    confidence: float = Field(ge=0, le=1)
    speaker: str | None
    speaker_confidence: float | None = Field(default=None, ge=0, le=1)


class _ClaudePage(BaseModel):
    texts: list[_ClaudeText]


_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "texts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "kind": {"type": "string", "enum": [k.value for k in TextKind]},
                    "x": {"type": "number"},
                    "y": {"type": "number"},
                    "width": {"type": "number"},
                    "height": {"type": "number"},
                    "language": {"type": ["string", "null"]},
                    "confidence": {"type": "number"},
                    "speaker": {"type": ["string", "null"]},
                    "speaker_confidence": {"type": ["number", "null"]},
                },
                "required": [
                    "text",
                    "kind",
                    "x",
                    "y",
                    "width",
                    "height",
                    "language",
                    "confidence",
                    "speaker",
                    "speaker_confidence",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["texts"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class ModelPricing:
    """Tarifs USD par million de jetons (à vérifier au moment de l'activation)."""

    input_per_million: Decimal
    output_per_million: Decimal


CLAUDE_PRICING: dict[str, ModelPricing] = {
    "claude-opus-5-5": ModelPricing(Decimal("4"), Decimal("20")),
    "claude-sonnet-5-5": ModelPricing(Decimal("2"), Decimal("10")),
    "claude-haiku-5-5": ModelPricing(Decimal("0.10"), Decimal("0.50")),
}


class ClaudeVisionProvider:
    """Transcription et classification du texte d'une page par Claude.

    `client` est un `anthropic.AsyncAnthropic` (injecté : les tests passent un double).
    Les refus de sécurité sont redirigés côté serveur vers un modèle de repli (`fallbacks`).
    """

    name = "claude"
    prompt_version = CLAUDE_PROMPT_VERSION

    def __init__(
        self,
        client: Any,
        *,
        model: str = "claude-opus-5-5",
        effort: str = "medium",
        max_output_tokens: int = 16000,
        estimated_output_tokens: int = 3000,
    ) -> None:
        if model not in CLAUDE_PRICING:
            raise ValueError(f"tarif inconnu pour {model} : ajouter-le à CLAUDE_PRICING")
        self._client = client
        self.model = model
        self._effort = effort
        self._max_tokens = max_output_tokens
        self._estimated_output = estimated_output_tokens

    @staticmethod
    def image_tokens(width: int, height: int) -> int:
        # Les images sont réduites côté API à ~1 568 px de grand côté ; ≈ (l * h) / 750 jetons.
        scale = min(1.0, 1568 / max(width, height))
        return int((width * scale) * (height * scale) / 750) + 1

    def _cost(self, input_tokens: int, output_tokens: int) -> Decimal:
        price = CLAUDE_PRICING[self.model]
        return (
            Decimal(input_tokens) * price.input_per_million
            + Decimal(output_tokens) * price.output_per_million
        ) / Decimal(1_000_000)

    def estimate_cost(self, context: PageContext) -> Decimal:
        prompt_tokens = 1200 + 40 * len(context.panels)
        return self._cost(
            self.image_tokens(context.width, context.height) + prompt_tokens,
            self._estimated_output,
        )

    def _user_content(self, context: PageContext) -> list[dict[str, Any]]:
        hints = {
            "reading_direction": context.direction.value,
            "language_hint": context.language_hint,
            "known_characters": context.known_characters,
            "detected_panels": [
                {
                    "index": p.index,
                    "x": round(p.bbox.x, 4),
                    "y": round(p.bbox.y, 4),
                    "width": round(p.bbox.width, 4),
                    "height": round(p.bbox.height, 4),
                }
                for p in context.panels
            ],
        }
        return [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/webp",
                    "data": base64.standard_b64encode(context.image_webp).decode("ascii"),
                },
            },
            {"type": "text", "text": "Page hints:\n" + json.dumps(hints, ensure_ascii=False)},
        ]

    async def analyze(self, context: PageContext) -> VisionResult:
        started = time.perf_counter()
        try:
            response = await self._client.beta.messages.create(
                model=self.model,
                max_tokens=self._max_tokens,
                system=CLAUDE_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": self._user_content(context)}],
                output_config={
                    "effort": self._effort,
                    "format": {"type": "json_schema", "schema": _OUTPUT_SCHEMA},
                },
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except Exception as exc:  # erreurs réseau / API : réessayables par la file
            raise VisionProviderError(f"appel Claude en échec : {type(exc).__name__}") from exc

        if response.stop_reason == "refusal":
            raise VisionProviderError("page refusée par le modèle", permanent=True)
        if response.stop_reason == "max_tokens":
            raise VisionProviderError("réponse tronquée (max_tokens)", permanent=True)
        text = next((b.text for b in response.content if b.type == "text"), None)
        if text is None:
            raise VisionProviderError("réponse sans texte", permanent=True)
        try:
            page = _ClaudePage.model_validate_json(text)
        except ValidationError as exc:
            raise VisionProviderError(f"JSON invalide : {exc.error_count()} erreur(s)") from exc

        texts = []
        for item in page.texts:
            width = min(item.width, 1.0 - item.x)
            height = min(item.height, 1.0 - item.y)
            if width <= 0 or height <= 0:
                continue  # boîte hors page : écartée plutôt qu'inventée
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
        usage = response.usage
        return VisionResult(
            texts=texts,
            provider=self.name,
            model=str(response.model),
            prompt_version=self.prompt_version,
            cost_usd=self._cost(usage.input_tokens, usage.output_tokens),
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            latency_ms=(time.perf_counter() - started) * 1000,
        )


class PaidProviderRefusedError(LookupError):
    """Fournisseur payant demandé alors que le mode zéro coût est actif."""


FREE_PROVIDERS = frozenset({"fake", "ollama", "human"})


def create_vision_provider(
    name: str,
    *,
    model: str | None = None,
    zero_cost: bool = True,
    ollama_url: str = "http://localhost:11434",
) -> PageVisionProvider:
    if name == "fake":
        return FakeVisionProvider()
    if name == "ollama":
        from primestone.vision.ollama import OllamaVisionProvider

        return OllamaVisionProvider(base_url=ollama_url, model=model or "qwen2.5vl:7b")
    if name == "claude":
        if zero_cost:
            raise PaidProviderRefusedError(
                "mode zéro coût actif : le fournisseur payant « claude » est refusé "
                "(PRIMESTONE_ZERO_COST=false pour l'autoriser)"
            )
        import anthropic

        return ClaudeVisionProvider(anthropic.AsyncAnthropic(), model=model or "claude-opus-5-5")
    raise LookupError(f"fournisseur vision inconnu : {name} (connus : fake, ollama, claude)")
