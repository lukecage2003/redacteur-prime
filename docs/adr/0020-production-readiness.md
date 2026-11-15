# ADR-0020 — Préparation à la production : IAP vérifié, GCS sans clé, intégrations, PDFium sérialisé

- Statut : Accepté
- Date : 2026-11-15

## Décision

1. **Authentification** : l'application n'est exposée que derrière un équilibreur de charge
   protégé par **Identity-Aware Proxy**. L'API vérifie en plus l'en-tête
   `x-goog-iap-jwt-assertion` sur chaque requête HTTP et chaque WebSocket :
   - signature ES256 avec les clés publiques de Google ;
   - émetteur, audience et expiration contrôlés ;
   - seules les sondes `/api/v1/health*` sont exemptées.

   `PRIMESTONE_IAP_AUDIENCE` est obligatoire hors développement. Nouvelle dépendance :
   `cryptography` (vérification ECDSA ; bibliothèque de référence, maintenue par la PyCA).
2. **Stockage GCS** (`GCSObjectStore`) :
   - API JSON de Cloud Storage ;
   - jeton du compte de service fourni par le serveur de métadonnées de Cloud Run : aucune
     clé JSON, aucune dépendance ;
   - bucket privé ; copies locales en flux pour les gros PDF ;
   - `PRIMESTONE_GCS_BUCKET` obligatoire pour `storage_backend=gcs`.
3. **API d'intégration** versionnée (`contract: 1.0`), en lecture seule :
   - Panel Explorer : cases et textes d'une page ;
   - Motion Studio : scripts **validés** uniquement (409 pour un brouillon).
4. **En-têtes de sécurité** web : X-Frame-Options DENY, nosniff, Referrer-Policy, HSTS, COOP,
   Permissions-Policy (micro autorisé pour la voix). Pas de CSP stricte : Next.js exige des
   nonces, à traiter au premier déploiement.
5. **PDFium sérialisé** par un verrou de processus : bibliothèque non thread-safe ; une
   segmentation fault est apparue en CI quand des workers rendaient en parallèle.
6. **Déploiement** : les workflows (inactifs) exigent `GCS_BUCKET`, `IAP_AUDIENCE` et les
   fournisseurs IA, et les transmettent aux services. **Aucune ressource n'est créée sans
   l'accord explicite du propriétaire.**

## Conséquences

- Restent à faire au premier déploiement (BLOCKED, ressources payantes) : test de charge, coûts
  réels, restauration de sauvegarde testée, CSP à nonces.
  Voir `docs/operations/production-checklist.md`.
