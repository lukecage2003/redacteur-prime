# SECURITY

## Signaler un problème

Projet personnel : signaler directement au propriétaire du dépôt (issue privée ou
« Security advisory » GitHub). Ne jamais publier un secret dans une issue.

## Contexte

Usage **personnel et non commercial**. Les comics analysés sont des œuvres protégées par le
droit d'auteur : ils sont stockés uniquement dans un bucket Cloud Storage privé, jamais dans Git,
jamais redistribués. Les contenus produits (scripts, analyses) citent leurs sources.

## Secrets

- Aucun secret dans le dépôt, les images Docker, les logs ou les messages d'erreur.
- Développement : fichier `.env` local (ignoré par Git). Cloud : Secret Manager, monté par Cloud Run.
- GitHub → GCP : Workload Identity Federation, **aucune clé JSON** de compte de service.
- Détection : gitleaks à chaque PR et chaque semaine (`security.yml`).
- Clé YouTube Data API (`PRIMESTONE_YOUTUBE_API_KEY`) : `SecretStr`, jamais recopiée dans les
  erreurs ni les traces de collecte ; Secret Manager dans le cloud.

## GitHub Actions

- Permissions par défaut `contents: read` ; élévations par job uniquement.
- `id-token: write` seulement dans `deploy-staging` et `deploy-production`.
- Actions tierces épinglées par SHA de commit ; mises à jour via Dependabot.
- `persist-credentials: false` sur les checkouts.
- Pas de `pull_request_target`, aucun secret exposé au code des forks.
- Production : environnement GitHub `production` avec approbation humaine obligatoire.

## Application

- Accès restreint par Identity-Aware Proxy (compte Google du propriétaire) ; services Cloud Run
  déployés avec `--no-allow-unauthenticated`.
- Conteneurs exécutés en utilisateur non root.
- Base Cloud SQL sur IP privée, authentification IAM ; buckets privés, accès uniforme,
  URL signées à courte durée pour l'affichage des pages.
- Fichiers importés traités comme hostiles (phase 2) : format détecté par signature, taille et
  nombre de pages bornés, PDF ouverts avec PDFium, archives CBZ jamais extraites sur disque,
  rejet des chemins suspects, des entrées chiffrées, des taux de compression anormaux et des
  images géantes ; noms de fichiers client réduits à leur nom de base ; clés de stockage validées.
- Les configurations staging/production refusent le fournisseur IA simulé et l'URL de base locale.

## Fournisseurs IA et résidence des données

L'infrastructure est en europe-west1 (UE). Les appels aux fournisseurs IA externes peuvent traiter
des données hors UE : avant d'activer un fournisseur, vérifier et consigner dans
`docs/operations/ai-providers.md` ses conditions de rétention et de non-utilisation pour
l'entraînement. Envoyer le minimum nécessaire (une page ou une case, pas un comic entier).
La vision (phase 3) envoie une page rendue à la fois, uniquement sur lancement explicite avec
budget ; aucun appel n'a lieu en CI ni par défaut (`PRIMESTONE_VISION_PROVIDER=fake`).

## Données et migrations

- Aucune migration destructive sans ADR, sauvegarde vérifiée et accord explicite.
- Sauvegardes automatiques Cloud SQL + restauration testée avant la mise en production (phase 13).
- Aucune donnée personnelle de tiers collectée ; les données de marché sont publiques ou issues de
  comptes Primestone autorisés.

## Dépendances

Audit `pip-audit` et `pnpm audit` (`security.yml`), CodeQL (Python, TypeScript, Actions),
Dependabot hebdomadaire.
