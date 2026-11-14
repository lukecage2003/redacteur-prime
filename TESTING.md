# TESTING

## Niveaux

| Niveau | Outil | Où | En CI |
|---|---|---|---|
| Unitaires Python | pytest | `*/tests/` | oui |
| Intégration (PostgreSQL + pgvector réels) | pytest `-m integration` | `*/tests/`, `db/tests/` | oui (service conteneur) |
| Migrations | Alembic + pytest | `db/tests/`, job `migrations` | oui |
| Unitaires web | Vitest | `apps/web/**/*.test.ts` | oui |
| Build | `next build`, `docker build` | jobs `web`, `docker` | oui |
| Évaluations IA réelles | scripts `eval/` | `eval/` | **non** (manuel, budgété) |

## Tests d'intégration

Ils s'exécutent si `PRIMESTONE_TEST_DATABASE_URL` est défini, sinon ils sont ignorés
(visible avec `-ra`). Garde-fou : le nom de la base doit contenir « test ».

```bash
docker compose up -d db
export PRIMESTONE_TEST_DATABASE_URL=postgresql+psycopg://primestone:primestone@localhost:5432/primestone_test
uv run pytest
```

Couverture actuelle de la file de tâches : idempotence, réservation concurrente sans doublon
(60 étapes, 6 workers), nouvelles tentatives différées, passage en DEAD, reprise après arrêt
brutal d'un worker (bail expiré), cohérence du statut du lot sous concurrence.

Couverture de la Comic Library : formats (signature, PDF corrompu, CBZ avec traversée de
chemin, bombe zip, image géante, image illisible, tri naturel, mise à l'échelle), stockage
(écriture atomique, clés malveillantes), pipeline complet (lot de 55 comics avec 4 workers,
reprise après arrêt brutal, doublons inter- et intra-lot, pages manquantes, page illisible,
fichiers rejetés), API (téléversement, rapport, navigation, image, chemins client ignorés).

Couverture Comic Vision : détecteur de cases sur planches synthétiques à vérité connue (LTR,
RTL, inclinées, page blanche, page pleine, bulle à cheval), rattachement et ordre des textes,
métriques (IoU, appariement, F1, ordre, CER), adaptateur Claude avec client simulé (requête,
schéma, coûts, refus, troncature, JSON invalide, erreurs réseau), pipeline (estimation, refus
au-delà du budget, budget revérifié avant chaque appel, jamais payé deux fois, échecs permanents
et transitoires, 4 workers en parallèle), API.

Couverture Forensic : extracteurs (preuve obligatoire, niveaux CANON/INTERPRETATION selon la
source, mentions insensibles aux accents et à la casse, premières attestations par document,
affirmations FR/EN, lettrage en capitales, contradictions avec rôles de preuve, identité
secrète, variantes de noms, clés stables), mode zéro coût, fournisseur Ollama (serveur simulé :
requête, conversion PNG, erreurs), transcription humaine (versions, cases invalides),
pipeline forensique (complétude, idempotence, corrections qui remplacent sans effacer, ordre
des tomes), API, et parcours complet dans un navigateur (formulaire, analyse, rapport).

Banc d'essai reproductible du détecteur : `uv run primestone-vision benchmark-panels --pages 200`.

Les comics de test sont **synthétiques** (générés par `conftest.py`) : aucune œuvre protégée.

## Fournisseurs IA

La CI n'utilise que `FakeLLMProvider` (déterministe, gratuit). Les validations réelles
(OCR, vision, scripts, voix) se font manuellement sur le corpus de référence avec un budget
explicite, et leurs résultats sont consignés dans `eval/results/` (phase 3+).

## Corpus de référence (`eval/`)

À constituer en phase 2–3 : un petit ensemble de comics possédés, annotés à la main (cases,
bulles, locuteurs, faits canoniques, contradictions volontaires). Les fichiers source ne sont
**pas** versionnés (droits d'auteur) ; seules les annotations et les empreintes SHA-256 le sont.

## Matrice de validation par phase

Voir les critères dans [ROADMAP.md](ROADMAP.md). Statut VALIDATED uniquement après
exécution sur cas réels et consignation des résultats.
