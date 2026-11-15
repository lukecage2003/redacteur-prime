# Adaptive Voice (phase 12)

Code : `packages/primestone/src/primestone/voice/` · ADR-0019 · coût : **nul**.

## Utilisation

- Web : `/voice`. Choisir une personnalité, puis taper une question ou **maintenir pour
  parler**. Le bouton « Interrompre » coupe la synthèse en cours.
- WebSocket : `/api/v1/ws/voice` (protocole décrit dans `apps/api/.../routes/voice.py`).

## Brancher la vraie voix (gratuit, sur ta machine)

La plateforme ne télécharge rien : installe les deux serveurs locaux toi-même.

1. Reconnaissance : lancer le serveur de **whisper.cpp** (`server -m <modèle>`), puis
   `PRIMESTONE_VOICE_STT=whisper_cpp` et `PRIMESTONE_WHISPER_CPP_URL=http://localhost:8080`.
2. Synthèse : lancer le serveur HTTP de **Piper** avec une voix française, puis
   `PRIMESTONE_VOICE_TTS=piper` et `PRIMESTONE_PIPER_URL=http://localhost:5000`.
3. Facultatif : `PRIMESTONE_EDITORIAL_WRITER=ollama` pour des réponses reformulées par un modèle
   local. Elles ne sont retenues que si elles passent le Fact Checker.

## Règles

- Réponses tirées des pages transcrites, citées, et vérifiées avant d'être dites.
- Sans source : « je ne sais pas ». Une erreur factuelle majeure est refusée.
- Seule la personnalité Brainstorming propose des hypothèses, toujours annoncées comme telles.

## Limites

- Tour de parole complet, sans transcription partielle en direct.
- Banc d'essai réel (latence, noms propres) : BLOCKED tant que les modèles ne sont pas
  installés.

## Tests

- `packages/primestone/tests/test_voice.py`
- `apps/api/tests/test_voice_ws.py`
- `apps/web/lib/voice.test.ts`
- Essai navigateur (mode texte).
