# Social Intelligence (phase 9)

Code : `packages/primestone/src/primestone/social/` · ADR-0016 · coût : **nul**.

## Utilisation

1. Approuver un livrable (dossier, audit, revue de théorie, dossier de recherche).
2. Le décliner :
   - web : bouton « Décliner pour YouTube, TikTok, Instagram » sur la mission ;
   - CLI : `uv run primestone-editorial social MISSION_ID --process` ;
   - API : `POST /api/v1/editorial/missions` avec `{"type": "SOCIAL_PACKAGE", "source_mission_id": "…", "platforms": [...]}`.
3. Relire le paquet (Fact Checker inclus), puis approuver ou rejeter.

## Sorties par plateforme

| Plateforme | Structure | Choix éditorial |
|---|---|---|
| YouTube (long, 16:9) | 1 chapitre par section du livrable + sources en description | avertit s'il y a moins de 3 chapitres (règle YouTube) |
| TikTok (9:16) | accroche (tension en priorité) → 2 faits d'autres sections → question | 30–60 s, durée estimée à ~150 mots/min |
| Instagram Reels (9:16) | même trame, **autre sélection** que TikTok | 30–60 s |
| Instagram carrousel (4:5) | couverture + 1 fait sourcé par carte + carte des sources | 20 cartes au plus |

## Règles

- Seules les phrases vérifiées sont reprises, mot pour mot, avec leur référence.
- Formats vérifiés le 2026-11-14 et marqués « à revérifier avant publication ».

## Limites

- Ce sont des trames sourcées, pas des scripts rédigés (phase 10).
- Sans tension ni affirmation dans le livrable, l'accroche est un fait simple.

## Tests

- `packages/primestone/tests/test_social_strategy.py`
- `apps/worker/tests/test_social_pipeline.py`
- `apps/web/lib/editorial.test.ts`
