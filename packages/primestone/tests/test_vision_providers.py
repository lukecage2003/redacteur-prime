import json
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import pytest

from primestone.provenance import BoundingBox
from primestone.vision import Panel, TextKind
from primestone.vision.providers import (
    ClaudeVisionProvider,
    FakeVisionProvider,
    PageContext,
    PageVisionProvider,
    VisionProviderError,
    create_vision_provider,
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


CONTEXT = PageContext(
    image_webp=b"RIFF....WEBP",
    width=1552,
    height=2400,
    panels=[Panel(index=1, bbox=BoundingBox(x=0.05, y=0.05, width=0.9, height=0.4))],
    language_hint="en",
)


@dataclass
class Block:
    type: str
    text: str = ""


@dataclass
class Usage:
    input_tokens: int = 2500
    output_tokens: int = 1200


@dataclass
class Response:
    content: list[Block]
    stop_reason: str = "end_turn"
    model: str = "claude-opus-5-5"
    usage: Usage = field(default_factory=Usage)


class StubMessages:
    def __init__(self, response: Response | Exception) -> None:
        self.response = response
        self.requests: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Response:
        self.requests.append(kwargs)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class StubClient:
    def __init__(self, response: Response | Exception) -> None:
        self.beta = type("Beta", (), {})()
        self.beta.messages = StubMessages(response)


def claude_json(texts: list[dict[str, Any]]) -> Response:
    return Response(content=[Block("thinking"), Block("text", json.dumps({"texts": texts}))])


ITEM = {
    "text": "I AM THE NIGHT.",
    "kind": "DIALOGUE",
    "x": 0.1,
    "y": 0.1,
    "width": 0.3,
    "height": 0.1,
    "language": "en",
    "confidence": 0.97,
    "speaker": "Batman",
    "speaker_confidence": 0.8,
}


@pytest.mark.anyio
async def test_fake_provider() -> None:
    provider = FakeVisionProvider(cost_per_page_usd=Decimal("0.01"))
    assert isinstance(provider, PageVisionProvider)
    result = await provider.analyze(CONTEXT)
    assert (result.texts, result.cost_usd, result.provider) == ([], Decimal("0.01"), "fake")


@pytest.mark.anyio
async def test_claude_parses_structured_output() -> None:
    client = StubClient(claude_json([ITEM]))
    provider = ClaudeVisionProvider(client)
    result = await provider.analyze(CONTEXT)

    assert len(result.texts) == 1
    region = result.texts[0]
    assert (region.text, region.kind, region.speaker) == (
        "I AM THE NIGHT.",
        TextKind.DIALOGUE,
        "Batman",
    )
    assert result.cost_usd == Decimal("0.034")  # 2 500 x 4 $/M + 1 200 x 20 $/M
    assert (result.input_tokens, result.output_tokens) == (2500, 1200)

    request = client.beta.messages.requests[0]
    assert request["model"] == "claude-opus-5-5"
    assert request["fallbacks"] == "default"
    assert request["betas"] == ["server-side-fallback-2026-07-01"]
    assert request["output_config"]["format"]["type"] == "json_schema"
    assert request["output_config"]["effort"] == "medium"
    image = request["messages"][0]["content"][0]
    assert image["source"]["media_type"] == "image/webp"
    hints = request["messages"][0]["content"][1]["text"]
    assert '"language_hint": "en"' in hints
    assert '"detected_panels"' in hints


@pytest.mark.anyio
async def test_claude_clips_boxes_and_drops_impossible_ones() -> None:
    overflowing = {**ITEM, "x": 0.9, "width": 0.3}
    outside = {**ITEM, "x": 1.0, "width": 0.2}
    no_speaker = {**ITEM, "speaker": None, "speaker_confidence": 0.4}
    result = await ClaudeVisionProvider(
        StubClient(claude_json([overflowing, outside, no_speaker]))
    ).analyze(CONTEXT)
    assert len(result.texts) == 2
    assert result.texts[0].bbox.x + result.texts[0].bbox.width == pytest.approx(1.0)
    assert result.texts[1].speaker_confidence is None


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("response", "permanent"),
    [
        (Response(content=[Block("text", "{}")], stop_reason="refusal"), True),
        (Response(content=[Block("text", "{")], stop_reason="max_tokens"), True),
        (Response(content=[Block("thinking")]), True),
        (Response(content=[Block("text", '{"texts": [{"text": ""}]}')]), False),
        (ConnectionError("réseau"), False),
    ],
)
async def test_claude_errors(response: Response | Exception, permanent: bool) -> None:
    with pytest.raises(VisionProviderError) as info:
        await ClaudeVisionProvider(StubClient(response)).analyze(CONTEXT)
    assert info.value.permanent is permanent


def test_claude_estimate_and_pricing() -> None:
    provider = ClaudeVisionProvider(StubClient(claude_json([])))
    assert ClaudeVisionProvider.image_tokens(1552, 2400) < 2400  # image réduite côté API
    assert Decimal("0.03") < provider.estimate_cost(CONTEXT) < Decimal("0.15")
    cheaper = ClaudeVisionProvider(StubClient(claude_json([])), model="claude-haiku-5-5")
    assert cheaper.estimate_cost(CONTEXT) < provider.estimate_cost(CONTEXT)
    with pytest.raises(ValueError, match="tarif"):
        ClaudeVisionProvider(StubClient(claude_json([])), model="inconnu")


def test_factory() -> None:
    assert create_vision_provider("fake").name == "fake"
    with pytest.raises(LookupError):
        create_vision_provider("nope")
