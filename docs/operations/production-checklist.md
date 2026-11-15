# Checklist de mise en production

Rien ici n'est exécuté automatiquement. Chaque étape payante exige l'accord explicite du
propriétaire. En local, tout fonctionne déjà gratuitement.

## 1. Provisionnement (payant, sur accord)

- [ ] Projet GCP, région `europe-west1`, budget avec alertes.
  Voir [gcp-setup.md](gcp-setup.md) et [COSTS.md](../../COSTS.md).
- [ ] Cloud SQL PostgreSQL 16 + pgvector, sauvegardes automatiques et PITR.
- [ ] Bucket GCS **privé** (accès uniforme), cycle de vie sur `renders/`.
- [ ] Artifact Registry, Workload Identity Federation
  ([workload-identity-federation.md](workload-identity-federation.md)).
- [ ] Secret Manager : `primestone-database-url`.
- [ ] Équilibreur de charge HTTPS + **IAP** (accès réservé au propriétaire). Relever l'audience
  `/projects/NUMÉRO/global/backendServices/ID`.

## 2. Variables GitHub (environnements `staging` et `production`)

`GCP_PROJECT_ID`, `GCP_REGION`, `GCP_WIF_PROVIDER`, `GCP_DEPLOY_SERVICE_ACCOUNT`,
`GCP_SOURCE_REGISTRY` (production), `GCS_BUCKET`, `IAP_AUDIENCE`, `PRIMESTONE_AI_PROVIDER`,
`PRIMESTONE_VISION_PROVIDER`. Ajouter des « Required reviewers » sur l'environnement
`production`.

## 3. Avant d'ouvrir l'accès

- [ ] `deploy-staging`, puis migrations (job `primestone-migrate`), puis tests de fumée :
  santé, import, page, mission.
- [ ] Vérifier qu'une requête **sans** IAP reçoit 401, et une WebSocket sans IAP la fermeture
  1008.
- [ ] CSP à nonces sur le web (Next.js middleware), puis vérification des en-têtes.
- [ ] Test de charge léger (usage personnel : 1 utilisateur, imports par lots de 3 à 5 PDF).
- [ ] **Restauration de sauvegarde testée** : restaurer Cloud SQL dans une instance temporaire
  et lancer `alembic check`.
- [ ] Coûts réels relevés après 7 jours, comparés à COSTS.md.

## 4. Production

- [ ] `deploy-production` avec le SHA validé en staging (approbation humaine requise).
- [ ] Mettre à jour ROADMAP.md : statuts VALIDATED seulement après usage réel.
