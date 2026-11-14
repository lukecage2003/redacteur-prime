# ADR-0004 — File de tâches durable sur PostgreSQL

- Statut : Accepté
- Date : 2026-11-14

## Contexte

Les lots de 50 comics ou plus génèrent des milliers d'étapes (rendu, OCR, analyse) qui doivent
survivre aux pannes, ne jamais être traitées en double et pouvoir être reprises.

## Décision

Tables `pipeline_run` et `pipeline_step` dans PostgreSQL ; réservation par
`UPDATE … WHERE id = (SELECT … FOR UPDATE SKIP LOCKED LIMIT 1)` ; clé d'idempotence unique ;
nouvelles tentatives bornées et différées ; baux (`locked_at`) récupérés par `recover_stale`
après un arrêt brutal ; verrou sur la ligne du lot pour garder un statut cohérent sous
concurrence. Le worker tourne en Cloud Run (worker pool) et/ou en Cloud Run Jobs pour les lots.

## Alternatives considérées

- **Pub/Sub** : excellent pour la diffusion d'événements, mais l'état d'avancement et
  l'idempotence doivent de toute façon vivre en base ; ajoute un composant et un coût.
- **Cloud Tasks** : bon contrôle de débit, mêmes remarques.
- **Celery/Redis** : un service supplémentaire à exploiter (Memorystore payant).

## Conséquences

Même comportement en local, en CI et dans le cloud ; état d'avancement interrogeable en SQL.
Limite : quelques centaines d'étapes par seconde — très au-delà du besoin. Si nécessaire,
Pub/Sub sera ajouté comme mécanisme de réveil derrière la même interface (nouvel ADR).
