# Moteur d'émissions (phase 21)

ADR-0028 · paquet `primestone.shows` · migration 0016.

## Ce que fait le module

- Cycle de vie gouverné : DRAFT, TESTING, ACTIVE, SUSPENDED, RETIRED ; chaque transition est
  une décision du fondateur.
- Règles versionnées (`show_guideline_version`), approuvées puis réversibles.
- Formats par plateforme et par langue, avec plage de durée et structure.
- Épisodes : format, langue, version des règles, conformité, statut jusqu'à la publication
  déclarée.
- Performance agrégée par émission, langue et format ; adéquation d'un sujet aux émissions et
  aux piliers.

## Utilisation

Pour démarrer : `uv run primestone-brand bootstrap` propose 3 piliers (Enquêtes, Comprendre,
Théories et débats) et 4 émissions en brouillon (PRIMESTONE COSMOS, THE COMIC FILES, BEYOND
THE PANEL, THE VERDICT) — des concepts à reprendre, chacun soumis à ta décision.

```bash
uv run primestone-creative series-create serie.json      # brouillon + décision DRAFT → TESTING
uv run primestone-brand approve DECISION_ID
uv run primestone-shows format SERIES_ID format.json
uv run primestone-creative episode SERIES_ID SCRIPT_ID --format-id FORMAT_ID
uv run primestone-shows final-validation SERIES_ID 1     # puis primestone-brand approve
uv run primestone-shows published SERIES_ID 1 CONTENT_ID
uv run primestone-shows performance SERIES_ID
uv run primestone-shows fit "Le mystère de Despair"
```

Web : lien depuis `/creative` vers `/shows/[id]` (état, transition proposable, formats,
épisodes et conformité, performance).

## Limites

- L'adéquation est lexicale ; un modèle local pourra l'affiner sans changer la règle.
- La durée d'un épisode est estimée à 150 mots par minute.
