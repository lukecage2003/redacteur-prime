# Architecture GCP

> Rien n'est provisionné. Ce document décrit la cible ; la création se fera après approbation
> explicite du plan et du budget (voir COSTS.md).

## Région

europe-west1 (UE). Vérifier au provisionnement la disponibilité de chaque service utilisé.

## Ressources (projet `primestone-staging`, puis `primestone-prod` si nécessaire)

| Ressource | Nom | Configuration |
|---|---|---|
| Artifact Registry (Docker) | `primestone` | europe-west1, nettoyage des images > 30 jours non déployées |
| Cloud Run service | `primestone-web` | min 0, max 2, `--no-allow-unauthenticated`, derrière IAP |
| Cloud Run service | `primestone-api` | min 0, max 2, IAP, connecteur Cloud SQL |
| Cloud Run worker pool | `primestone-worker` | 0–1 instance, démarré à la demande pour les lots |
| Cloud Run Job | `primestone-migrate` | `alembic upgrade head`, lancé par le déploiement |
| Cloud Run Job | `primestone-batch` | lots de comics, tâches parallèles |
| Cloud SQL | `primestone` | PostgreSQL 16, pgvector, IP privée, auth IAM, sauvegardes quotidiennes, PITR |
| Cloud Storage | `<projet>-library` | privé, accès uniforme, versionnement, PDF/CBZ source |
| Cloud Storage | `<projet>-renders` | privé, pages rendues, cycle de vie |
| Secret Manager | `primestone-database-url`, clés fournisseurs IA | accès limité à `primestone-runtime` |
| Comptes de service | `primestone-runtime`, `primestone-deploy` | moindre privilège |
| Budget | `primestone-monthly` | alertes 50 / 90 / 100 % |

## IAM

| Compte | Rôles |
|---|---|
| `primestone-runtime` | `cloudsql.client`, `cloudsql.instanceUser`, `secretmanager.secretAccessor` (secrets ciblés), `storage.objectUser` (buckets ciblés), `logging.logWriter`, `monitoring.metricWriter` |
| `primestone-deploy` (WIF) | `run.developer`, `artifactregistry.writer`, `iam.serviceAccountUser` sur `primestone-runtime` uniquement |

## Accès utilisateur

Identity-Aware Proxy sur les services Cloud Run, limité au compte Google du propriétaire.
L'API vérifiera l'en-tête JWT signé d'IAP (défense en profondeur).

## Observabilité

Logs JSON structurés (corrélation par `run_id`/`step_id`/`mission_id`), métriques de file
(étapes PENDING, DEAD, latence), alertes : étapes DEAD, erreurs 5xx, dépense IA journalière.
