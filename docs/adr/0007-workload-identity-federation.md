# ADR-0007 — GitHub → GCP par Workload Identity Federation

- Statut : Accepté
- Date : 2026-11-14

## Décision

GitHub Actions s'authentifie auprès de GCP par OIDC via Workload Identity Federation. Aucune
clé JSON de compte de service. La condition d'attribut du fournisseur utilise les identifiants
**numériques** du dépôt et du propriétaire (résistants au renommage et à la réutilisation de nom),
et chaque compte de service de déploiement n'est usurpable que depuis l'environnement GitHub
correspondant (`staging` ou `production`). Seuls `deploy-staging.yml` et
`deploy-production.yml` reçoivent `id-token: write`.

Procédure : docs/operations/workload-identity-federation.md.

## Conséquences

Pas de secret longue durée à faire tourner. Une PR (même d'un fork) ne peut jamais obtenir
d'identité GCP : les environnements ne s'exécutent que depuis `main`.
