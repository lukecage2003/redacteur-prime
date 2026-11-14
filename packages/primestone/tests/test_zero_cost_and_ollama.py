import io
import json
from decimal import Decimal
from typing import Any

import httpx
import pytest
from PIL import Image

from primestone.config import Settings
from primestone.vision.ollama import OllamaVisionProvider
from primestone.vision.providers import (
    PageContext,
    PaidProviderRefusedError,
    VisionProviderError,
    create_vision_provider,
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def webp() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (40, 60), "white").save(buffer, format="WEBP")
    return buffer.getvalue()


CONTEXT = PageContext(image_webp=webp(), width=40, height=60, panels=[], language_hint="fr")


def test_zero_cost_is_the_default() -> None:
    assert Settings(_env_file=None).zero_cost is True


def test_paid_provider_refused_in_zero_cost_mode() -> None:
    with pytest.raises(PaidProviderRefusedError, match="zéro coût"):
        create_vision_provider("claude")
    assert create_vision_provider("ollama").estimate_cost(CONTEXT) == Decimal("0")


def transport(
    captured: list[dict[str, Any]], status: int = 200, content: str | None = None
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        answer = (
            content
            if content is not None
            else json.dumps(
                {
                    "texts": [
                        {
                            "text": "AU SECOURS !",
                            "kind": "DIALOGUE",
                            "x": 0.1,
                            "y": 0.1,
                            "width": 0.3,
                            "height": 0.1,
                            "language": "fr",
                            "confidence": 0.8,
                            "speaker": None,
                            "speaker_confidence": None,
                        }
                    ]
                }
            )
        )
        return httpx.Response(
            status,
            json={
                "model": "qwen2.5vl:7b",
                "message": {"content": answer},
                "prompt_eval_count": 900,
                "eval_count": 120,
            },
        )

    return httpx.MockTransport(handler)


@pytest.mark.anyio
async def test_ollama_provider_free_and_structured() -> None:
    captured: list[dict[str, Any]] = []
    provider = OllamaVisionProvider(transport=transport(captured))
    result = await provider.analyze(CONTEXT)
    assert result.cost_usd == Decimal("0")
    assert [t.text for t in result.texts] == ["AU SECOURS !"]
    assert (result.input_tokens, result.output_tokens) == (900, 120)
    request = captured[0]
    assert request["stream"] is False
    assert request["format"]["type"] == "object"  # sortie contrainte par schéma
    image = request["messages"][1]["images"][0]
    import base64

    assert base64.b64decode(image)[:8] == b"\x89PNG\r\n\x1a\n"  # WebP converti en PNG


@pytest.mark.anyio
async def test_ollama_errors() -> None:
    missing = OllamaVisionProvider(transport=transport([], status=404))
    with pytest.raises(VisionProviderError) as info:
        await missing.analyze(CONTEXT)
    assert info.value.permanent
    assert "ollama pull" in str(info.value)

    garbage = OllamaVisionProvider(transport=transport([], content="pas du json"))
    with pytest.raises(VisionProviderError, match="JSON"):
        await garbage.analyze(CONTEXT)

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refusé")

    offline = OllamaVisionProvider(transport=httpx.MockTransport(refuse))
    with pytest.raises(VisionProviderError, match="injoignable") as info:
        await offline.analyze(CONTEXT)
    assert not info.value.permanent
