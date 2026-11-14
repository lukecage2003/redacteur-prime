# Évaluation et corpus de référence

- `fixtures/` : petites données synthétiques pour la CI (aucune œuvre protégée).
- `corpus/` (non versionné) : comics possédés servant de référence ; seules les annotations
  et empreintes SHA-256 sont versionnées dans `annotations/`.
- `results/` : résultats datés des évaluations réelles (fournisseur, modèle, version de prompt,
  coût, métriques).

Les évaluations réelles sont lancées manuellement, avec budget ; jamais par la CI.
