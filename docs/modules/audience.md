# Audience Intelligence & communauté (phase 15)

Code : `packages/primestone/src/primestone/audience/` · ADR-0022 · coût : **nul**.

## Utilisation

```bash
uv run primestone-audience segment --name "Curieux du cosmique" --description "…" \
  --motivation "comprendre la cosmologie" --level INTERMEDIATE
uv run primestone-audience evidence SEG --kind METRIC --statement "Rétention 52 %" \
  --data '{"avg_view_percentage": 52, "videos": 6}' --class PRIVATE_AUTHORIZED
uv run primestone-audience collect           # commentaires publics de TA chaîne (clé gratuite)
uv run primestone-audience community         # questions, demandes, théories récurrentes
uv run primestone-audience link SEG --target-kind ENTITY --target ENTITY_ID --relation INTERESTED_IN --evidence EV
uv run primestone-audience brief --process   # note d'audience du Chief Editor
```

Web : `/audience`. API : `/api/v1/audience/*`.

## Règles

- Jamais d'âge : les segments se définissent par motivations et niveau de connaissance.
- CONFIRMED seulement avec au moins deux natures de preuves observées ; DECLARED reste une
  hypothèse.
- Aucune identité de commentateur conservée ; aucune interaction automatisée.

## Limites

- Classement des commentaires par marqueurs FR/EN : simple, explicable, imparfait (ironie).
- Reddit et forums : non couverts (accès officiel requis).

## Tests

- `packages/primestone/tests/test_community.py`
- `apps/worker/tests/test_audience_pipeline.py`
- `apps/web/lib/audience.test.ts`
