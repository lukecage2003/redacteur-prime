"""WebSocket de l'assistant vocal (coût nul).

Protocole JSON :
  client → {"type": "start", "personality": "research", "language": "fr", "document_ids": [...]}
           {"type": "text", "text": "…"}                 (mode texte de secours)
           {"type": "audio", "wav": "<base64>"}           (un tour de parole complet, WAV)
           {"type": "interrupt"}                          (coupe la synthèse en cours)
  serveur → {"type": "ready"} · {"type": "transcript", "text"} · {"type": "answer", …}
           {"type": "sentence", "index", "text", "audio"?} · {"type": "done"}
           {"type": "interrupted"} · {"type": "error", "detail"}
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from primestone.voice import VoiceProviderError, VoiceSession
from primestone.voice.runtime import VoiceRuntime

router = APIRouter(tags=["voice"])
MAX_MESSAGE_BYTES = 28_000_000  # ~20 Mo d'audio en base64


async def _speak(ws: WebSocket, session: VoiceSession, sentences: list[str]) -> None:
    iterator = session.speak(sentences)
    while True:
        event = await asyncio.to_thread(next, iterator, None)  # synthèse hors boucle
        if event is None:
            break
        await ws.send_json(event)
        await asyncio.sleep(0)  # laisse passer une interruption
    await ws.send_json({"type": "interrupted" if session.interrupted else "done"})


@router.websocket("/ws/voice")
async def voice(ws: WebSocket) -> None:
    await ws.accept()
    runtime: VoiceRuntime = ws.app.state.voice
    session: VoiceSession | None = None
    speaking: asyncio.Task[None] | None = None
    try:
        while True:
            raw = await ws.receive_text()
            if len(raw) > MAX_MESSAGE_BYTES:
                await ws.send_json({"type": "error", "detail": "message trop volumineux"})
                continue
            try:
                message: dict[str, Any] = json.loads(raw)
                kind = message.get("type")
                if kind == "start":
                    session = runtime.session(
                        str(message.get("personality", "conversation")),
                        str(message.get("language", "fr")),
                        [UUID(str(d)) for d in message.get("document_ids", [])][:200],
                    )
                    await ws.send_json({"type": "ready", "personality": session.personality.key})
                    continue
                if session is None:
                    raise ValueError("session non démarrée (envoyer « start »)")
                if kind == "interrupt":
                    session.interrupt()
                    continue
                if kind not in ("text", "audio"):
                    raise ValueError(f"type de message inconnu : {kind}")
                if speaking and not speaking.done():
                    session.interrupt()  # un nouveau tour coupe la réponse précédente
                    await speaking
                if kind == "audio":
                    question = await asyncio.to_thread(session.hear, str(message.get("wav", "")))
                    await ws.send_json({"type": "transcript", "text": question})
                else:
                    question = str(message.get("text", ""))[:2000]
                answer = await session.answer(question)
                await ws.send_json({"type": "answer", **answer})
                speaking = asyncio.create_task(_speak(ws, session, answer["sentences"]))
            except (ValueError, VoiceProviderError) as exc:
                await ws.send_json({"type": "error", "detail": str(exc)})
    except WebSocketDisconnect:
        if speaking:
            speaking.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await speaking
