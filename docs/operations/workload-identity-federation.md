# Workload Identity Federation (GitHub Actions → GCP)

> **Ne pas exécuter sans autorisation explicite.** Commandes de référence pour le provisionnement.

## 1. Identifiants numériques du dépôt

Récupérer `id` et `owner.id` depuis `https://api.github.com/repos/lukecage2003/redacteur-prime`.

```bash
PROJECT_ID=primestone-staging
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
REPO_ID=<id numérique du dépôt>
OWNER_ID=<id numérique du propriétaire>
```

## 2. Pool et fournisseur

```bash
gcloud iam workload-identity-pools create github \
  --project "$PROJECT_ID" --location global --display-name "GitHub Actions"

gcloud iam workload-identity-pools providers create-oidc redacteur-prime \
  --project "$PROJECT_ID" --location global --workload-identity-pool github \
  --issuer-uri "https://token.actions.githubusercontent.com" \
  --attribute-mapping "google.subject=assertion.sub,attribute.repository_id=assertion.repository_id,attribute.repository_owner_id=assertion.repository_owner_id,attribute.environment=assertion.environment,attribute.ref=assertion.ref" \
  --attribute-condition "assertion.repository_id == '${REPO_ID}' && assertion.repository_owner_id == '${OWNER_ID}' && assertion.ref == 'refs/heads/main'"
```

## 3. Liaison au compte de déploiement, limitée à l'environnement

```bash
gcloud iam service-accounts add-iam-policy-binding \
  "primestone-deploy@${PROJECT_ID}.iam.gserviceaccount.com" \
  --project "$PROJECT_ID" --role roles/iam.workloadIdentityUser \
  --member "principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github/attribute.environment/staging"
```

(Pour la production : projet `primestone-prod`, `attribute.environment/production`.)

## 4. Variables de l'environnement GitHub `staging`

| Variable | Valeur |
|---|---|
| `GCP_PROJECT_ID` | `primestone-staging` |
| `GCP_REGION` | `europe-west1` |
| `GCP_WIF_PROVIDER` | `projects/<PROJECT_NUMBER>/locations/global/workloadIdentityPools/github/providers/redacteur-prime` |
| `GCP_DEPLOY_SERVICE_ACCOUNT` | `primestone-deploy@primestone-staging.iam.gserviceaccount.com` |

Ce sont des **variables**, pas des secrets : aucune n'est sensible. Pour la production, ajouter
`GCP_SOURCE_REGISTRY` (registre de staging) et accorder à l'agent de service Cloud Run de prod
`artifactregistry.reader` sur ce registre.
