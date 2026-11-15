# Creative Intelligence (phase 18)

Code : `packages/primestone/src/primestone/creative/` · ADR-0025 · coût : **nul**.

## Utilisation

```bash
uv run primestone-creative charter                         # charte en vigueur
uv run primestone-creative charter-publish charte.json --name "Primestone v1"
uv run primestone-creative series-create serie.json        # promesse, identité, ton, structure…
uv run primestone-creative episode SERIES_ID SCRIPT_ID
uv run primestone-script evaluate SCRIPT_ID                # d'abord : faits vérifiés
uv run primestone-creative package SCRIPT_ID               # 10 titres, 5 miniatures, promesses, accroches
uv run primestone-creative review SCRIPT_ID --process      # mission du Chief Editor
```

Web : `/creative` (charte, séries) ; sur la page d'un script, « Proposer titres et
miniatures ».

## Format de la charte (`charte.json`)

`colors` [{name, hex, usage}], `fonts`, `tone` {do, dont}, `thumbnail` {max_words,
max_faces…}, `packaging` {title_max_chars}, `sound`, `motion`. Partir de la charte par défaut
(`primestone-creative charter`) et la personnaliser.

## Règles

- Titre refusé s'il promet ce que le script ne contient pas, ou s'il contient un terme banni.
- Aucune prédiction de CTR : les tests proposés se mènent avec « Tester et comparer », puis
  `primestone-performance experiment-*`.
- Miniatures : concepts décrits, contrôlés selon la charte ; aucune image générée.

## Tests

- `packages/primestone/tests/test_packaging.py`
- `apps/worker/tests/test_creative_pipeline.py`
- `apps/web/lib/creative.test.ts`
