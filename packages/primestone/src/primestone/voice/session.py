"""Session vocale : tour de parole → réponse ancrée → phrases → synthèse, interruptible.

Réponse par défaut GRATUITE et déterministe : passages trouvés par la recherche hybride
(transcriptions servies), cités mot pour mot avec leur page, puis vérifiés par le Fact Checker.
Un modèle local (Ollama) peut reformuler ; sa réponse n'est dite que si elle passe le Fact
Checker, sinon la réponse sourcée est conservée. Rien n'est inventé : sans passage, l'assistant
dit qu'il ne sait pas.
"""

from __future__ import annotations

import base64
from collections.abc import Awaitable, Callable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from primestone.editorial.factcheck import Corpus, check_text, split_sentences
from primestone.voice.personalities import PERSONALITIES, Personality
from primestone.voice.providers import STTProvider, TTSProvider

Searcher = Callable[[str, Sequence[UUID]], list[dict[str, Any]]]
CorpusLoader = Callable[[Sequence[UUID]], Corpus]
Rephraser = Callable[[str, str], Awaitable[str]]

UNKNOWN = {
    "fr": "Je ne trouve rien à ce sujet dans les pages transcrites : je préfère ne pas inventer.",
    "en": "I can't find this in the transcribed pages, so I won't make anything up.",
}
SPECULATION = {
    "fr": "Hypothèse à vérifier, pas un fait : ",
    "en": "Hypothesis to check, not a fact: ",
}


@dataclass
class VoiceSession:
    personality: Personality
    language: str
    document_ids: list[UUID]
    search: Searcher
    corpus: CorpusLoader
    titles: dict[str, str]
    stt: STTProvider | None = None
    tts: TTSProvider | None = None
    rephrase: Rephraser | None = None
    interrupted: bool = False
    history: list[dict[str, str]] = field(default_factory=list)

    @classmethod
    def start(cls, personality: str, **kwargs: Any) -> VoiceSession:
        if personality not in PERSONALITIES:
            raise ValueError(f"personnalité inconnue : {personality}")
        if kwargs.get("language") not in ("fr", "en"):
            raise ValueError("langue attendue : fr ou en")
        return cls(personality=PERSONALITIES[personality], **kwargs)

    def hear(self, wav_b64: str) -> str:
        if self.stt is None:
            raise ValueError("aucun fournisseur de reconnaissance vocale : mode texte uniquement")
        try:
            wav = base64.b64decode(wav_b64, validate=True)
        except ValueError:
            raise ValueError("audio base64 invalide") from None
        if len(wav) > 20_000_000:
            raise ValueError("audio trop long (20 Mo maximum)")
        return self.stt.transcribe(wav, language=self.language)

    def _grounded(self, question: str) -> str:
        hits = [h for h in self.search(question, self.document_ids) if h["kind"] == "TEXT"]
        if not hits:
            return UNKNOWN[self.language]
        limit = self.personality.max_sentences
        lines = []
        for hit in hits[:limit]:
            title = self.titles.get(hit["document_id"], "?")
            panel = f", case {hit['panel']}" if hit["panel"] else ""
            lines.append(f"« {hit['content']} » [{title}, p. {hit['page']}{panel}].")
        return " ".join(lines)

    async def answer(self, question: str) -> dict[str, Any]:
        """Réponse vérifiée ; `sentences` est la file à synthétiser (interruptible)."""
        self.interrupted = False
        question = question.strip()
        if not question:
            raise ValueError("question vide")
        grounded = self._grounded(question)
        text, author = grounded, "sources"
        corpus = self.corpus(self.document_ids)
        if self.rephrase is not None and grounded != UNKNOWN[self.language]:
            try:
                candidate = await self.rephrase(self.personality.style, grounded)
            except Exception:  # le modèle est facultatif : réponse sourcée conservée
                candidate = ""
            if candidate and check_text(candidate, corpus).verdict != "FAIL":
                text, author = candidate, "modèle local vérifié"
        if self.personality.may_speculate and grounded == UNKNOWN[self.language]:
            text = SPECULATION[self.language] + UNKNOWN[self.language]
        report = check_text(text, corpus)
        if report.verdict == "FAIL":  # garde-fou : jamais dire une erreur factuelle majeure
            text, author = UNKNOWN[self.language], "refus (erreur factuelle)"
            report = check_text(text, corpus)
        self.history += [{"role": "user", "text": question}, {"role": "assistant", "text": text}]
        return {
            "text": text,
            "author": author,
            "personality": self.personality.key,
            "sentences": split_sentences(text),
            "fact_check": {"verdict": report.verdict.value, "counts": report.counts},
        }

    def interrupt(self) -> None:
        """Arrêt immédiat de la synthèse en cours (barge-in)."""
        self.interrupted = True

    def speak(self, sentences: Sequence[str]) -> Iterator[dict[str, Any]]:
        """Synthèse phrase par phrase ; s'arrête dès qu'une interruption est demandée."""
        for index, sentence in enumerate(sentences):
            if self.interrupted:
                return
            event: dict[str, Any] = {"type": "sentence", "index": index, "text": sentence}
            if self.tts is not None:
                audio = self.tts.synthesize(sentence, language=self.language)
                event["audio"] = base64.b64encode(audio).decode("ascii")
            yield event
