# Distribution et portefeuille (phase 23)

ADR-0030 · paquet `primestone.distribution` · migration 0018.

## Ce que fait le module

- Canaux par plateforme et par langue, avec l'état d'autorisation des statistiques.
- Plan de diffusion proposé, approuvé par le fondateur, puis publié **déclaré** par lui.
- Portefeuille : parts visées par pilier, niveau, langue, émission ; déséquilibres signalés.
- Performance agrégée par canal.

## Utilisation

```bash
uv run primestone-distribution channel-add YOUTUBE fr @primestone "PRIMESTONE FR" --stats CSV_EXPORT
uv run primestone-distribution propose CHANNEL_ID "Despair" --script-id SCRIPT_ID --at 2026-12-01T18:00:00+01:00
uv run primestone-brand approve DECISION_ID
uv run primestone-distribution declare ITEM_ID https://youtu.be/xxxx xxxx   # après publication
uv run primestone-distribution portfolio-create decembre.json
uv run primestone-distribution portfolio PORTFOLIO_ID
```

`decembre.json` : `{"name": "Décembre", "period_start": "2026-12-01", "period_end":
"2026-12-31", "targets": {"language": {"fr": 0.7, "en": 0.3}, "level": {"DISCOVERY": 0.5}}}`.

Web : `/distribution` (plan, déclarations, canaux et performance).

## Limites

- Aucune publication automatique, par conception.
- Le portefeuille compte des éléments du plan, pas des durées ni des audiences.
