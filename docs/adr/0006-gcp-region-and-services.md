# ADR-0006 — GCP europe-west1 et services managés

- Statut : Accepté
- Date : 2026-11-14

## Décision

Région de référence **europe-west1** (Belgique, UE) : Cloud Run, Cloud SQL, Cloud Storage,
Secret Manager, Artifact Registry, Logging et Monitoring y sont disponibles. Services :
Cloud Run (web, api, worker, jobs), Cloud SQL PostgreSQL 16 + pgvector, Cloud Storage
(buckets privés), Secret Manager, Artifact Registry, Cloud Logging/Monitoring, IAP pour l'accès.
Pub/Sub non utilisé au départ (ADR-0004).

Projets : `staging` d'abord (sert d'environnement personnel), `production` créé seulement si
nécessaire. Développement : local (Docker), pas de projet GCP dédié.

## Points à vérifier au provisionnement

- Disponibilité régionale des modèles Vertex AI si utilisés.
- Fournisseurs IA hors GCP : traitement potentiellement hors UE (voir SECURITY.md).

## Conséquences

Coûts réduits ; aucune ressource créée avant autorisation explicite et budget validé.
