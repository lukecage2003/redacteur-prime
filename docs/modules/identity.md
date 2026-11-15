# Identité indépendante (phase 22)

ADR-0029 · paquet `primestone.identity` · migration 0017.

## Ce que fait le module

- Voix de marque sous licence (synthétiques locales ou humaines autorisées par écrit),
  approuvées par le fondateur ; jamais la voix du fondateur par défaut.
- Profils visuels versionnés par émission, plateforme et langue.
- Règles par langue : une règle FR ne s'applique jamais à un contenu EN.
- Plan de narration et synthèse locale facultative (Piper).

## Utilisation

```bash
uv run primestone-identity voice-propose voix.json   # licence et usage autorisé obligatoires
uv run primestone-brand approve DECISION_ID
uv run primestone-identity visual-add regles.json --language fr
uv run primestone-identity visual-resolve --language en --platform YOUTUBE
uv run primestone-identity narrate SCRIPT_ID --synthesize   # PRIMESTONE_VOICE_TTS=piper
```

Exemple de `voix.json` : `{"name": "Voix FR", "language": "fr", "tone": "posé",
"kind": "SYNTHETIC", "provider": "piper", "voice": "<modèle local>", "license": "<licence
recopiée depuis la fiche du modèle>", "allowed_use": "narration non commerciale"}`.

Web : section « Identité de marque » sur `/creative`.

## Limites

- Aucune voix n'est fournie : le modèle Piper et sa licence sont à choisir par le fondateur.
- Le service ne juge pas la licence : il exige qu'elle soit enregistrée et approuvée.
