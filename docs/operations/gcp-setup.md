# Provisionnement GCP — procédure

> Statut : **non exécuté**. Chaque étape payante nécessite l'accord explicite du propriétaire.

1. Créer le projet `primestone-staging`, lier la facturation, créer le budget mensuel
   avec alertes 50/90/100 %.
2. Activer les API : `run`, `sqladmin`, `artifactregistry`, `secretmanager`, `iamcredentials`,
   `sts`, `iap`, `storage`, `logging`, `monitoring`.
3. Créer Artifact Registry `primestone` (europe-west1).
4. Créer les comptes `primestone-runtime` et `primestone-deploy` et leurs rôles
   (docs/architecture/gcp.md).
5. Workload Identity Federation (workload-identity-federation.md).
6. Cloud SQL PostgreSQL 16 (plus petite configuration), IP privée, auth IAM, sauvegardes ;
   la migration 0001 active `vector`.
7. Secret `primestone-database-url`.
8. Buckets `-library` et `-renders` (privés, accès uniforme).
9. Environnement GitHub `staging` + variables ; lancer `deploy-staging` manuellement.
10. Activer IAP sur les services, limité au compte du propriétaire.

Ces étapes seront codées en Terraform (`infra/terraform/`) au moment du provisionnement, pour
être reproductibles et relues en PR.
