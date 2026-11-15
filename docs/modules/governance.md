# Brand Intelligence et gouvernance (phase 20)

ADR-0027 · paquet `primestone.governance` · migration 0015.

## Ce que fait le module

- **Marque** : `media_brand` PRIMESTONE (mission, langues FR/EN, langue principale FR).
- **Piliers éditoriaux** : proposés (PROPOSED), activés (ACTIVE) ou retirés (RETIRED) par
  décision `PILLAR_CHANGE`.
- **Politiques** : par action, approbation exigée ou non. Sensibles par défaut :
  CHARTER_CHANGE, PILLAR_CHANGE, SHOW_LIFECYCLE, SCRIPT_FINAL_VALIDATION, DISTRIBUTION_PLAN,
  VOICE_PROFILE, COST_SETTINGS, POLICY_CHANGE.
- **Journal des décisions** : PROPOSED → APPROVED / REJECTED → REVERTED, auteur, décideur,
  date, motif, version de politique, état antérieur.
- **Charte** : chaque version publiée est un brouillon soumis au fondateur.

## Utilisation

```bash
uv run primestone-brand policies
uv run primestone-brand pillar "Enquêtes" "Une question, des preuves page par page"
uv run primestone-brand decisions --status PROPOSED
uv run primestone-brand approve DECISION_ID
uv run primestone-brand revert DECISION_ID --reason "retour à la charte précédente"
```

Web : `/governance` (journal, boutons Approuver / Rejeter / Annuler, piliers, politiques).

## Limites

- Une seule marque utilisée aujourd'hui ; le modèle en accepte plusieurs.
- Les effets des actions des phases 21 à 24 arrivent avec leurs gestionnaires.
