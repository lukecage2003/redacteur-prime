"""Plongements vectoriels GRATUITS pour la recherche hybride.

- `HashingEmbedder` (défaut) : n-grammes de caractères et mots hachés dans 256 dimensions,
  calculé localement, sans modèle ni téléchargement. Robuste aux fautes de frappe et aux
  variantes d'orthographe ; ce n'est PAS une similarité sémantique.
- `OllamaEmbedder` : vrai modèle sémantique open source exécuté localement (ex.
  `nomic-embed-text`), gratuit, sur la machine de l'utilisateur.
"""

from __future__ import annotations

import hashlib
import math
from typing import Protocol, runtime_checkable

import httpx

from primestone.forensic.extract import fold


@runtime_checkable
class Embedder(Protocol):
    name: str
    dimensions: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def _bucket(token: str, dimensions: int) -> tuple[int, float]:
    digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
    value = int.from_bytes(digest, "big")
    return value % dimensions, 1.0 if (value >> 63) & 1 else -1.0


class HashingEmbedder:
    def __init__(self, dimensions: int = 256) -> None:
        self.dimensions = dimensions
        self.name = f"hashing-ngram-{dimensions}@2"

    def _one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        folded = fold(text)
        for word in folded.split():
            index, sign = _bucket(f"w:{word}", self.dimensions)
            vector[index] += sign  # poids mesuré : 1,0 (2,0 pénalisait trop les fautes de frappe)
            padded = f" {word} "
            for i in range(len(padded) - 2):
                index, sign = _bucket(f"c:{padded[i : i + 3]}", self.dimensions)
                vector[index] += sign
        norm = math.sqrt(sum(v * v for v in vector))
        return [v / norm for v in vector] if norm else vector

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]


class OllamaEmbedder:
    def __init__(
        self,
        *,
        base_url: str = "http://localhost:11434",
        model: str = "nomic-embed-text",
        dimensions: int = 768,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.dimensions = dimensions
        self.name = f"ollama:{model}"
        self._model = model
        self._client = httpx.Client(base_url=base_url.rstrip("/"), timeout=120, transport=transport)

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self._client.post("/api/embed", json={"model": self._model, "input": texts})
        response.raise_for_status()
        vectors: list[list[float]] = response.json()["embeddings"]
        if any(len(v) != self.dimensions for v in vectors):
            raise ValueError(f"dimension inattendue (attendu {self.dimensions})")
        return vectors


def to_pgvector(vector: list[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in vector) + "]"
