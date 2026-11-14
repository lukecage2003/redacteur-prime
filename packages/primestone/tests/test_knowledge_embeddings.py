import json
import math

import httpx
import pytest

from primestone.knowledge import HashingEmbedder, OllamaEmbedder
from primestone.knowledge.embeddings import to_pgvector


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def test_hashing_is_deterministic_and_normalized() -> None:
    embedder = HashingEmbedder()
    a, b = embedder.embed(["Je suis Batman", "Je suis Batman"])
    assert a == b
    assert math.isclose(math.sqrt(sum(v * v for v in a)), 1.0, rel_tol=1e-9)
    assert len(a) == 256
    assert embedder.name == "hashing-ngram-256@2"


def test_hashing_tolerates_typos_accents_and_case() -> None:
    embedder = HashingEmbedder()
    batman, typo, other = embedder.embed(
        ["BATMAN", "Batmann", "Superman vole au-dessus de la ville"]
    )
    assert cosine(batman, typo) > 0.5
    assert cosine(batman, other) < 0.2
    elodie, accent = embedder.embed(["Élodie", "elodie"])
    assert cosine(elodie, accent) > 0.99


def test_empty_text() -> None:
    assert HashingEmbedder(8).embed([""]) == [[0.0] * 8]


def test_ollama_embedder_with_stub() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["model"] == "nomic-embed-text"
        return httpx.Response(200, json={"embeddings": [[0.1, 0.2, 0.3] for _ in body["input"]]})

    embedder = OllamaEmbedder(dimensions=3, transport=httpx.MockTransport(handler))
    assert embedder.embed(["a", "b"]) == [[0.1, 0.2, 0.3], [0.1, 0.2, 0.3]]
    wrong = OllamaEmbedder(dimensions=4, transport=httpx.MockTransport(handler))
    with pytest.raises(ValueError, match="dimension"):
        wrong.embed(["a"])


def test_pgvector_literal() -> None:
    assert to_pgvector([0.5, -1.0]) == "[0.500000,-1.000000]"
