"""Fournisseurs vocaux interchangeables, GRATUITS : simulés (tests) ou serveurs locaux.

- STT : serveur HTTP de whisper.cpp (`POST /inference`, multipart, WAV) ;
- TTS : serveur HTTP de Piper (`POST /` avec le texte, renvoie un WAV).
Les modèles s'installent sur la machine du propriétaire ; la plateforme ne télécharge rien.
"""

from __future__ import annotations

import io
import struct
import wave
from typing import Protocol, runtime_checkable

import httpx


class VoiceProviderError(RuntimeError):
    pass


@runtime_checkable
class STTProvider(Protocol):
    name: str

    def transcribe(self, wav: bytes, *, language: str) -> str: ...


@runtime_checkable
class TTSProvider(Protocol):
    name: str

    def synthesize(self, text: str, *, language: str) -> bytes: ...


def silent_wav(seconds: float = 0.1, rate: int = 16_000) -> bytes:
    """WAV mono 16 bits silencieux (tests, fournisseur simulé)."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack("<h", 0) * int(seconds * rate))
    return buffer.getvalue()


class FakeSTT:
    """Simulé : renvoie un texte scripté (le « contenu » audio n'est pas analysé)."""

    name = "fake"

    def __init__(self, transcript: str = "Qui est Selina ?") -> None:
        self.transcript = transcript
        self.calls = 0

    def transcribe(self, wav: bytes, *, language: str) -> str:
        if not wav.startswith(b"RIFF"):
            raise VoiceProviderError("audio attendu au format WAV")
        self.calls += 1
        return self.transcript


class FakeTTS:
    name = "fake"

    def __init__(self) -> None:
        self.spoken: list[str] = []

    def synthesize(self, text: str, *, language: str) -> bytes:
        self.spoken.append(text)
        return silent_wav(0.05 * max(1, len(text.split())))


class WhisperCppSTT:
    name = "whisper_cpp"

    def __init__(self, base_url: str, *, transport: httpx.BaseTransport | None = None) -> None:
        self._client = httpx.Client(base_url=base_url, timeout=60, transport=transport)

    def transcribe(self, wav: bytes, *, language: str) -> str:
        try:
            response = self._client.post(
                "/inference",
                files={"file": ("audio.wav", wav, "audio/wav")},
                data={"language": language, "response_format": "json", "temperature": "0"},
            )
        except httpx.HTTPError as exc:
            raise VoiceProviderError(f"whisper.cpp injoignable ({type(exc).__name__})") from None
        if response.status_code != 200:
            raise VoiceProviderError(f"whisper.cpp a refusé l'audio (HTTP {response.status_code})")
        return str(response.json().get("text", "")).strip()


class PiperTTS:
    name = "piper"

    def __init__(self, base_url: str, *, transport: httpx.BaseTransport | None = None) -> None:
        self._client = httpx.Client(base_url=base_url, timeout=60, transport=transport)

    def synthesize(self, text: str, *, language: str) -> bytes:
        try:
            response = self._client.post("/", content=text.encode("utf-8"))
        except httpx.HTTPError as exc:
            raise VoiceProviderError(f"Piper injoignable ({type(exc).__name__})") from None
        if response.status_code != 200 or not response.content.startswith(b"RIFF"):
            raise VoiceProviderError(f"Piper n'a pas renvoyé de WAV (HTTP {response.status_code})")
        return response.content
