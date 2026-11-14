# Module Forensic Intelligence (phase 4) — coût nul

Code : `packages/primestone/src/primestone/forensic/` · CLI : `primestone-forensic`
· API : `/api/v1/forensic/*`, `PUT …/pages/{n}/transcription` · Web : `/library/{id}/forensic`
et formulaire de transcription sur chaque page.

## Chaîne entièrement gratuite

```
Transcription : humaine (web/API)  ou  modèle local Ollama  ou  [Claude, désactivé]
      │
      ▼
Extracteurs à règles (aucun modèle) ─► observations + preuves exactes ─► rapport
```

## Utilisation

```bash
# 1. Transcrire (web : page → « Transcrire / corriger ») ou modèle local gratuit :
ollama pull qwen2.5vl:7b
PRIMESTONE_VISION_PROVIDER=ollama uv run primestone-vision analyze --documents <ID> --budget 0 --process
# 2. Analyse forensique (tomes dans l'ordre de lecture) :
uv run primestone-forensic analyze --documents <TOME1> <TOME2> --character Batman
uv run primestone-forensic report  --documents <TOME1> <TOME2>
uv run primestone-forensic observations --documents <TOME1> --kind CONTRADICTION_CANDIDATE
```

## Observations produites

| Type | Exemple | Niveau |
|---|---|---|
| LETTERING | Réplique : « Je suis Batman. » | CANON si humain ou confiance ≥ 0,9, sinon INTERPRETATION |
| SPEECH | Bruce dit : « … » | CANON si attribution humaine, sinon INTERPRETATION |
| MENTION | Le nom « Robin » est écrit | niveau de la transcription |
| FIRST_APPEARANCE | Robin attesté pour la première fois p. 2 | INTERPRETATION si document incomplet |
| CLAIM | Selina affirme avoir 28 ans (affirmation, non vérifiée) | niveau de l'attribution |
| CONTRADICTION_CANDIDATE | 28 / 31 ans ; « Selina » / « Catwoman » | INTERPRETATION, avec explications alternatives |
| ALIAS_CANDIDATE | « Catwoman » / « Cat-Woman » | INTERPRETATION, confiance = similarité |

## Garanties

- Aucune observation sans preuve (refusé par construction).
- Ré-exécution idempotente (`observation_key`), historique conservé.
- Rapport `INCOMPLETE` tant qu'une page n'est pas transcrite ; pages manquantes listées.
- Ordre des documents respecté (tome 1 avant tome 2) pour « qui l'a dit en premier ».
- Le lettrage en capitales (« I AM HUNGRY ») ne produit pas de fausse revendication d'identité.

## Limites

Règles d'affirmation étroites (âge, identité, FR/EN) ; pas encore d'objets, de lieux, de
symboles ni de transitions narratives (nécessitent une analyse visuelle ou du texte transcrit
plus riche) ; les théories relèvent de la phase 7.
