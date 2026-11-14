# Module Editorial Director (phase 6) — coût nul

Code : `packages/primestone/src/primestone/editorial/` · Étape worker : `editorial.run_mission`
· CLI : `primestone-editorial` · API : `/api/v1/editorial/*` · Web : `/editorial`.

## Missions

| Type | Plan (agents) | Livrable |
|---|---|---|
| Dossier de personnage | Research Director → Character Researcher → Continuity Editor → Chief Editor (rédaction) → Fact Checker | dossier sourcé : présence, affirmations, liens, contradictions, pages manquantes |
| Audit de continuité | Research Director → Comics Analyst → Continuity Editor → Chief Editor → Fact Checker | liste sourcée des contradictions candidates, variantes de noms, lacunes |
| Vérification d'un texte | Research Director → Fact Checker | verdict phrase par phrase |
| Revue de théorie (phase 7) | Research Director → Theory Researcher → Chief Editor → Fact Checker | preuves, contre-preuves, alternatives, candidats à classer, recommandation (maintenir, rétrograder, contestée, réfutée, à corriger) |
| Note de marché (phase 8) | Market Analyst → Chief Editor | écarts EN→FR chiffrés et expliqués, sources publiques, sujets sans données ; jamais « VALIDER » sans réserve (estimations) |
| Dossier de recherche (phase 7) | Research Director → Theory Researcher → Chief Editor → Fact Checker | sources citées pour une question, sans conclusion |

Recommandation du Chief Editor : **VALIDER**, **VALIDER AVEC RÉSERVES** (points à relire, pages
manquantes, agent en échec) ou **NE PAS VALIDER** (erreur factuelle majeure — l'approbation est
alors impossible).

## Format de citation vérifié

```
Selina affirme : « Je suis Catwoman. » [Nuit noire #1, p. 2, case 2].
« Encore toi ? » [p. 1]           (titre facultatif s'il n'y a qu'un document)
```

Statuts : VERIFIED, QUOTE_NOT_FOUND, INVALID_CITATION, CONFLICTS_WITH_EVIDENCE (erreurs majeures
en gras dans l'interface), PAGE_NOT_TRANSCRIBED, PARAPHRASE, NO_CITATION, NOT_FACTUAL (titres,
lignes « Note : », questions).

## Utilisation

```bash
uv run primestone-editorial dossier --documents <T1> <T2> --character "Selina" --process
uv run primestone-editorial check --documents <T1> --draft mon-script.md --process
uv run primestone-editorial approve <APPROVAL_ID> --comment "ok"
# Rédaction par modèle local gratuit (facultatif) :
ollama pull qwen2.5:7b && export PRIMESTONE_EDITORIAL_WRITER=ollama
```

## Limites

Pas de résolution des pronoms (« Elle a 40 ans » est signalé NON SOURCÉ, pas comparé) ; les
paraphrases ne sont pas vérifiées sémantiquement (relecture humaine) ; les agents des phases 7 à
11 sont listés mais indisponibles.
