# ADR-0019 — Adaptive Voice : fournisseurs locaux gratuits, réponses ancrées et vérifiées

- Statut : Accepté
- Date : 2026-11-15

## Décision

1. **Fournisseurs interchangeables** (`STTProvider`, `TTSProvider`) :
   - simulés pour la CI ;
   - serveurs **locaux et gratuits** : whisper.cpp (`/inference`) pour la reconnaissance,
     Piper (HTTP) pour la synthèse.

   La plateforme ne télécharge **aucun modèle** : le propriétaire les installe sur sa machine.
2. **Réponse ancrée** :
   - passages trouvés par la recherche hybride (transcriptions servies), cités mot pour mot
     avec leur page ;
   - **vérifiée par le Fact Checker avant d'être dite** ; en cas d'erreur majeure, refus
     explicite ;
   - sans passage : « je ne sais pas », jamais d'invention ;
   - un modèle local (Ollama, zéro coût) peut reformuler, mais sa version n'est retenue que si
     elle passe le Fact Checker.
3. **Cinq personnalités** (Conversation, Research, Editorial, Director, Brainstorming) : ton et
   longueur. Seule Brainstorming peut proposer des hypothèses, toujours annoncées comme telles.
4. **WebSocket `/api/v1/ws/voice`** :
   - un tour de parole = un WAV (ou du texte) ;
   - réponse découpée en phrases, synthétisées une à une ;
   - **interruption** : un nouveau tour ou `interrupt` coupe la synthèse en cours ;
   - **mode texte de secours** toujours disponible.
5. **Web** `/voice` : micro du navigateur, maintenir pour parler (WAV 16 kHz encodé côté
   client), lecture en file, bouton d'interruption.

## Conséquences

- Pas de streaming STT partiel (tour complet) : latence d'un tour plus longue, plus simple et
  plus fiable. À réévaluer après le banc d'essai.
- Banc STT/TTS réel (latence, noms propres FR/EN) : BLOCKED tant que les modèles locaux ne sont
  pas installés par le propriétaire.
