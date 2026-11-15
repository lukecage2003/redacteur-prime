"""Adaptive Voice (phase 12) : assistant vocal gratuit (fournisseurs locaux), 5 personnalités,
réponses ancrées et vérifiées, interruption, mode texte de secours."""

from primestone.voice.personalities import PERSONALITIES, Personality
from primestone.voice.providers import (
    FakeSTT,
    FakeTTS,
    PiperTTS,
    STTProvider,
    TTSProvider,
    VoiceProviderError,
    WhisperCppSTT,
    silent_wav,
)
from primestone.voice.session import UNKNOWN, VoiceSession

__all__ = [
    "PERSONALITIES",
    "UNKNOWN",
    "FakeSTT",
    "FakeTTS",
    "Personality",
    "PiperTTS",
    "STTProvider",
    "TTSProvider",
    "VoiceProviderError",
    "VoiceSession",
    "WhisperCppSTT",
    "silent_wav",
]
