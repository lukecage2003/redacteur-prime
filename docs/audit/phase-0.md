# Phase 0 — Audit du dépôt (2026-11-14)

## Constat

| Élément | État constaté |
|---|---|
| Dépôt | `lukecage2003/redacteur-prime` |
| Commits / branches distantes / PR | 0 / 0 / 0 — dépôt GitHub vide, sans branche par défaut |
| Code, dépendances, workflows, documentation | aucun |
| Fichiers sensibles | aucun |
| Conflits avec l'architecture cible | aucun (démarrage à zéro) |
| Outils disponibles | Python 3.13, uv 0.11, Node 22, pnpm 10, Docker, client psql 16 ; `gcloud` présent mais non authentifié ; Terraform absent |

## Décisions prises (validées par le propriétaire : « faire les meilleurs choix »)

| Sujet | Décision |
|---|---|
| Usage | Personnel, non commercial |
| Organisation du code | Monolithe modulaire, monorepo uv + pnpm (ADR-0001, 0002) |
| Données | PostgreSQL 16 + pgvector, graphe en relationnel (ADR-0003) |
| Asynchrone | File durable PostgreSQL ; Pub/Sub reporté (ADR-0004) |
| IA | Passerelle indépendante des fournisseurs, fournisseur simulé en CI (ADR-0005) |
| Cloud | GCP europe-west1 ; un seul environnement (staging) au départ (ADR-0006, COSTS.md) |
| Authentification CI → GCP | Workload Identity Federation, identifiants numériques (ADR-0007) |
| Git | Trunk-based, pas de `develop` (ADR-0008) |
| Accès à l'application | Identity-Aware Proxy, compte du propriétaire |
| Roadmap | Market Intelligence scindée (collecte en 2b) ; banc d'essai voix avancé en phase 6 |

## Points restant à la main du propriétaire

1. Créer la branche `main` (le dépôt est vide ; la session ne peut pas pousser sur `main`).
2. Visibilité du dépôt (public/privé) : conditionne dependency-review et les relecteurs
   obligatoires d'environnement.
3. Provisionnement GCP et compte de facturation : uniquement sur autorisation explicite.
4. Choix des fournisseurs IA réels après banc d'essai (phase 3).
5. Comptes Primestone à connecter (YouTube Analytics, etc.) en phase 2b/11.

## Risques

API sociales restrictives (TikTok Research API réservée aux chercheurs, Instagram limité aux
comptes propres), hallucinations dans l'analyse (parade : preuve obligatoire + Fact Checker),
dérive des coûts IA (parade : budget par mission, cache, estimation préalable), qualité de
l'OCR sur le lettrage manuscrit (parade : banc d'essai sur corpus annoté).
