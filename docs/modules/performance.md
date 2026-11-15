# Performance Intelligence (phase 11)

Code : `packages/primestone/src/primestone/performance/` · ADR-0018 · coût : **nul**.

## Utilisation

1. Dans YouTube Studio : Analytics → mode avancé → onglet Contenu → **Exporter (CSV)**.
2. Importer l'export :
   - web : `/performance` ;
   - CLI : `uv run primestone-performance import export.csv --from 2026-10-01 --to 2026-10-31`.
3. **Relier** chaque vidéo à son script (phase 10), sur la page web ou avec
   `primestone-performance link CONTENT_ID SCRIPT_ID`.
4. Lire le bilan : `primestone-performance report`, la page web, ou la mission du Chief Editor
   (`primestone-performance review --process`).

## Règles

- Chaîne Primestone uniquement (`PRIVATE_AUTHORIZED`, contrainte en base). Aucune métrique de
  concurrent.
- Colonnes CSV inconnues ignorées et listées. La durée de visionnage est convertie d'heures en
  minutes.
- Signaux calculés à partir de 5 vidéos reliées à un script noté ; |rho| ≥ 0,5 pour une
  recommandation. Une corrélation n'est pas une cause.

## Limites

- Les en-têtes de l'export Studio peuvent changer : les synonymes reconnus sont dans
  `importers.py`, et les colonnes ignorées sont signalées à chaque import.
- OAuth YouTube Analytics : le client existe et est testé, mais la connexion réelle reste à
  faire (BLOCKED).

## Tests

- `packages/primestone/tests/test_performance_learning.py`
- `apps/worker/tests/test_performance_pipeline.py`
- `apps/web/lib/performance.test.ts`

## Phase 14 — Mesure par objectif et expériences (ADR-0021)

### Brancher les statistiques complètes de ta chaîne (gratuit, lecture seule)

1. Dans Google Cloud Console (projet gratuit, aucune facturation) :
   - activer « YouTube Analytics API » et « YouTube Data API v3 » ;
   - créer un identifiant OAuth de type **Application de bureau** ;
   - mettre `PRIMESTONE_YOUTUBE_OAUTH_CLIENT_ID` et `PRIMESTONE_YOUTUBE_OAUTH_CLIENT_SECRET`
     dans `.env`.
2. `uv run primestone-performance authorize` : ouvrir l'adresse affichée, autoriser, puis
   copier la ligne `PRIMESTONE_YOUTUBE_OAUTH_REFRESH_TOKEN=…` dans `.env`. Ne jamais la
   partager.
3. `uv run primestone-performance sync --from 2026-10-01 --to 2026-10-31` : statistiques par
   vidéo et courbes de rétention.

### Objectifs

`primestone-performance objective CONTENT_ID --objective DISCOVERY --format LONG`, ou la
colonne « Objectif » de `/performance`. Puis `primestone-performance objectives` affiche
chaque vidéo comparée à ses pairs, sur les indicateurs de son objectif.

### Expériences

```bash
uv run primestone-performance experiment-create --title "Miniature" --hypothesis "…" --variable THUMBNAIL --metric ctr
uv run primestone-performance experiment-variant EXP --label A --description "visage" --exposures 30000 --successes 1800
uv run primestone-performance experiment-variant EXP --label B --description "objet" --exposures 30000 --successes 1350
uv run primestone-performance experiment-conclude EXP --conclusion "…" --next "…"
```

Résultat « Tester et comparer » sans comptes : `--share 0.55 --source YOUTUBE_TEST_COMPARE`.
Il est enregistré, mais n'est jamais déclaré démontré.

## Phase 19 — Content Performance Lab (ADR-0026)

```bash
uv run primestone-performance autopsy CONTENT_ID   # constats OBSERVED / HYPOTHESIS / DEMONSTRATED
uv run primestone-performance hooks                # accroches face à la rétention de début
uv run primestone-performance drop-offs            # décrochages par section
uv run primestone-performance returning            # spectateurs connus par objectif
uv run primestone-performance loop SCRIPT_ID       # boucle RESEARCH → … → OPTIMIZE
uv run primestone-performance validation           # les 13 critères de complétude
```

La page `/performance` affiche la validation : chaque critère est « démontré » ou montre ce
qui manque. La complétude se constate sur des données réelles, elle ne se déclare pas.
