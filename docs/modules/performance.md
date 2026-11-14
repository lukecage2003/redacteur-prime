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
