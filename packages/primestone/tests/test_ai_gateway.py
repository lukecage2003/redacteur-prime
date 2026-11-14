from decimal import Decimal

import pytest

from primestone.ai_gateway import (
    AIGateway,
    BudgetExceededError,
    CompletionRequest,
    FakeLLMProvider,
    LLMProvider,
    Message,
    ProviderRegistry,
    default_registry,
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def request(
    prompt_id: str = "comic.panel_summary", text: str = "Résume la case"
) -> CompletionRequest:
    return CompletionRequest(
        prompt_id=prompt_id, prompt_version="1.0.0", messages=[Message(role="user", content=text)]
    )


@pytest.mark.anyio
async def test_fake_provider_is_deterministic() -> None:
    provider = FakeLLMProvider()
    a = await provider.complete(request())
    b = await provider.complete(request())
    assert a.text == b.text
    assert a.provider == "fake"
    assert isinstance(provider, LLMProvider)


@pytest.mark.anyio
async def test_fake_provider_scripted_response() -> None:
    provider = FakeLLMProvider(responses={"comic.panel_summary": "Un héros sur un toit."})
    result = await provider.complete(request())
    assert result.text == "Un héros sur un toit."


@pytest.mark.anyio
async def test_gateway_records_calls_and_spend() -> None:
    gateway = AIGateway(FakeLLMProvider(cost_per_call_usd=Decimal("0.10")), Decimal("1.00"))
    await gateway.complete(request())
    await gateway.complete(request())
    assert gateway.spent_usd == Decimal("0.20")
    assert len(gateway.records) == 2
    record = gateway.records[0]
    assert (record.prompt_id, record.prompt_version) == ("comic.panel_summary", "1.0.0")
    assert record.error is None


@pytest.mark.anyio
async def test_gateway_refuses_call_over_budget_before_calling() -> None:
    provider = FakeLLMProvider(cost_per_call_usd=Decimal("0.60"))
    gateway = AIGateway(provider, Decimal("1.00"))
    await gateway.complete(request())
    with pytest.raises(BudgetExceededError):
        await gateway.complete(request())
    assert len(provider.calls) == 1  # le second appel n'a jamais atteint le fournisseur


@pytest.mark.anyio
async def test_gateway_records_failures() -> None:
    gateway = AIGateway(FakeLLMProvider(fail_with=TimeoutError("lent")), Decimal("1"))
    with pytest.raises(TimeoutError):
        await gateway.complete(request())
    assert gateway.records[0].error == "TimeoutError: lent"
    assert gateway.spent_usd == 0


def test_negative_budget_rejected() -> None:
    with pytest.raises(ValueError, match="budget"):
        AIGateway(FakeLLMProvider(), Decimal("-1"))


def test_registry() -> None:
    registry = default_registry()
    assert registry.names() == ["fake", "ollama"]
    assert registry.create("fake").name == "fake"
    with pytest.raises(LookupError, match="inconnu"):
        registry.create("nope")
    with pytest.raises(ValueError, match="déjà"):
        registry.register("fake", FakeLLMProvider)


def test_empty_registry_message() -> None:
    with pytest.raises(LookupError, match="aucun"):
        ProviderRegistry().create("x")


@pytest.mark.anyio
async def test_zero_cost_gateway_refuses_paid_calls() -> None:
    paid = AIGateway(
        FakeLLMProvider(cost_per_call_usd=Decimal("0.01")), Decimal("10"), zero_cost=True
    )
    with pytest.raises(BudgetExceededError, match="zéro coût"):
        await paid.complete(request())
    free = AIGateway(FakeLLMProvider(), Decimal("0"), zero_cost=True)
    assert (await free.complete(request())).usage.cost_usd == 0


@pytest.mark.anyio
async def test_ollama_llm_provider_free() -> None:
    import json

    import httpx

    from primestone.ai_gateway.ollama import OllamaLLMProvider

    seen: list[dict[str, object]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(json.loads(req.content))
        return httpx.Response(
            200,
            json={
                "model": "qwen2.5:7b",
                "message": {"content": "Bonjour."},
                "prompt_eval_count": 12,
                "eval_count": 3,
            },
        )

    provider = OllamaLLMProvider(transport=httpx.MockTransport(handler))
    result = await AIGateway(provider, Decimal("0"), zero_cost=True).complete(
        CompletionRequest(
            prompt_id="t",
            prompt_version="1",
            system="Sois bref.",
            messages=[Message(role="user", content="Salut")],
        )
    )
    assert (result.text, result.usage.cost_usd, result.usage.output_tokens) == ("Bonjour.", 0, 3)
    assert seen[0]["messages"][0] == {"role": "system", "content": "Sois bref."}
    assert seen[0]["stream"] is False
