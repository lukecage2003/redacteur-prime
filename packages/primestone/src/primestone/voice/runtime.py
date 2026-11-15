"""Assemblage d'une session vocale depuis la configuration (fournisseurs gratuits)."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Engine, text

from primestone.ai_gateway import AIGateway, CompletionRequest, Message, default_registry
from primestone.config import Settings
from primestone.editorial.factcheck import Corpus
from primestone.forensic import ForensicService
from primestone.knowledge import KnowledgeService, hybrid_search
from primestone.voice.providers import (
    FakeSTT,
    FakeTTS,
    PiperTTS,
    STTProvider,
    TTSProvider,
    WhisperCppSTT,
)
from primestone.voice.session import Rephraser, VoiceSession

REPHRASE_PROMPT_ID = "voice.rephrase"
REPHRASE_SYSTEM = (
    "Tu es l'assistant vocal d'une rédaction comics. Reformule la réponse fournie pour l'oral, "
    "dans ce style : {style}. Garde À L'IDENTIQUE chaque citation entre « » et chaque référence "
    "entre crochets juste après. N'ajoute aucun fait."
)


class VoiceRuntime:
    def __init__(self, settings: Settings, engine: Engine, knowledge: KnowledgeService) -> None:
        self._settings = settings
        self._engine = engine
        self._knowledge = knowledge
        self._forensic: ForensicService = knowledge.forensic

    def _stt(self) -> STTProvider | None:
        if self._settings.voice_stt == "whisper_cpp":
            return WhisperCppSTT(self._settings.whisper_cpp_url)
        return FakeSTT()

    def _tts(self) -> TTSProvider | None:
        if self._settings.voice_tts == "piper":
            return PiperTTS(self._settings.piper_url)
        return FakeTTS() if self._settings.voice_tts == "fake" else None

    def _rephraser(self) -> Rephraser | None:
        if self._settings.editorial_writer == "none":
            return None
        provider = default_registry(
            ollama_url=self._settings.ollama_url, ollama_model=self._settings.ollama_text_model
        ).create(self._settings.editorial_writer)
        gateway = AIGateway(provider, Decimal("0"), zero_cost=True)

        async def rephrase(style: str, grounded: str) -> str:
            result = await gateway.complete(
                CompletionRequest(
                    prompt_id=REPHRASE_PROMPT_ID,
                    prompt_version="1.0.0",
                    system=REPHRASE_SYSTEM.format(style=style),
                    messages=[Message(role="user", content=grounded)],
                    max_output_tokens=600,
                    temperature=0.3,
                )
            )
            return result.text

        return rephrase

    def corpus(self, document_ids: Sequence[UUID]) -> Corpus:
        if not document_ids:
            return Corpus(titles={}, page_counts={}, rows=[])
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT d.id, c.title, d.page_count FROM document d "
                    "JOIN comic c ON c.id = d.comic_id WHERE d.id = ANY(:ids)"
                ),
                {"ids": list(document_ids)},
            ).all()
        return Corpus(
            titles={r[0]: r[1] for r in rows},
            page_counts={r[0]: r[2] or 0 for r in rows},
            rows=self._forensic.text_rows(document_ids),
            claims=self._forensic.observations(document_ids, kind="CLAIM", limit=10_000),
        )

    def session(
        self, personality: str, language: str, document_ids: Sequence[UUID]
    ) -> VoiceSession:
        corpus = self.corpus(document_ids)
        if len(corpus.titles) != len(set(document_ids)):
            raise ValueError("document inconnu")

        def search(question: str, docs: Sequence[UUID]) -> list[dict[str, Any]]:
            return hybrid_search(
                self._engine, self._knowledge.embedder, question, document_ids=docs, limit=8
            )

        return VoiceSession.start(
            personality,
            language=language,
            document_ids=list(document_ids),
            search=search,
            corpus=self.corpus,
            titles={str(k): v for k, v in corpus.titles.items()},
            stt=self._stt(),
            tts=self._tts(),
            rephrase=self._rephraser(),
        )
