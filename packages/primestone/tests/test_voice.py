import asyncio
import base64
from uuid import uuid4

import httpx
import pytest

from primestone.editorial import Corpus
from primestone.forensic import TextRow
from primestone.provenance import BoundingBox
from primestone.voice import (
    PERSONALITIES,
    UNKNOWN,
    FakeSTT,
    FakeTTS,
    PiperTTS,
    VoiceProviderError,
    VoiceSession,
    WhisperCppSTT,
    silent_wav,
)

DOC = uuid4()
ROW = TextRow(
    id=uuid4(),
    analysis_id=uuid4(),
    document_id=DOC,
    page=2,
    order=1,
    panel_index=1,
    kind="DIALOGUE",
    text="Je suis Catwoman.",
    language="fr",
    confidence=1.0,
    speaker="Selina",
    speaker_confidence=1.0,
    bbox=BoundingBox(x=0.1, y=0.1, width=0.2, height=0.2),
    human=True,
)
CORPUS = Corpus(titles={DOC: "Nuit noire #1"}, page_counts={DOC: 3}, rows=[ROW])
HIT = {
    "kind": "TEXT",
    "document_id": str(DOC),
    "page": 2,
    "panel": 1,
    "content": "Je suis Catwoman.",
}


def session(personality: str = "research", hits: list | None = None, rephrase=None) -> VoiceSession:
    return VoiceSession.start(
        personality,
        language="fr",
        document_ids=[DOC],
        search=lambda q, d: [HIT] if hits is None else hits,
        corpus=lambda d: CORPUS,
        titles={str(DOC): "Nuit noire #1"},
        stt=FakeSTT("Qui est Catwoman ?"),
        tts=FakeTTS(),
        rephrase=rephrase,
    )


def test_five_personalities() -> None:
    assert set(PERSONALITIES) == {
        "conversation",
        "research",
        "editorial",
        "director",
        "brainstorming",
    }
    assert [p.key for p in PERSONALITIES.values() if p.may_speculate] == ["brainstorming"]
    with pytest.raises(ValueError, match="personnalité"):
        session("pirate")


def test_grounded_answer_is_cited_and_verified() -> None:
    s = session()
    answer = asyncio.run(s.answer("Qui est Catwoman ?"))
    assert answer["text"] == "« Je suis Catwoman. » [Nuit noire #1, p. 2, case 1]."
    assert answer["fact_check"]["verdict"] == "PASS"
    events = list(s.speak(answer["sentences"]))
    assert events[0]["text"] == answer["text"]
    assert base64.b64decode(events[0]["audio"]).startswith(b"RIFF")


def test_unknown_never_invented_and_speculation_labelled() -> None:
    assert asyncio.run(session(hits=[]).answer("Qui est Batman ?"))["text"] == UNKNOWN["fr"]
    brainstorm = asyncio.run(session("brainstorming", hits=[]).answer("Et si ?"))
    assert brainstorm["text"].startswith("Hypothèse à vérifier, pas un fait")


def test_model_rephrasing_kept_only_if_verified() -> None:
    async def good(style: str, grounded: str) -> str:
        return f"Selina le dit clairement : {grounded}"

    async def liar(style: str, grounded: str) -> str:
        return "Selina dit « Je suis Batman. » [Nuit noire #1, p. 2, case 1]."

    kept = asyncio.run(session(rephrase=good).answer("Qui ?"))
    assert kept["author"] == "modèle local vérifié"
    refused = asyncio.run(session(rephrase=liar).answer("Qui ?"))
    assert refused["author"] == "sources"  # la version du modèle est écartée
    assert "Batman" not in refused["text"]


def test_interrupt_stops_speech() -> None:
    s = session()
    events = s.speak(["Une.", "Deux.", "Trois."])
    assert next(events)["index"] == 0
    s.interrupt()
    assert list(events) == []


def test_hear_validates_audio() -> None:
    s = session()
    wav = base64.b64encode(silent_wav()).decode()
    assert s.hear(wav) == "Qui est Catwoman ?"
    with pytest.raises(ValueError, match="base64"):
        s.hear("pas du base64 !")
    with pytest.raises(VoiceProviderError, match="WAV"):
        s.hear(base64.b64encode(b"MP3...").decode())


def test_local_http_providers() -> None:
    seen: list[httpx.Request] = []

    def whisper(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"text": " Bonjour. "})

    stt = WhisperCppSTT("http://w", transport=httpx.MockTransport(whisper))
    assert stt.transcribe(silent_wav(), language="fr") == "Bonjour."
    assert seen[0].url.path == "/inference"
    tts = PiperTTS(
        "http://p",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, content=silent_wav())),
    )
    assert tts.synthesize("Salut", language="fr").startswith(b"RIFF")
    broken = PiperTTS("http://p", transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    with pytest.raises(VoiceProviderError, match="WAV"):
        broken.synthesize("x", language="fr")
