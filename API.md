# API

API HTTP FastAPI, versionnée sous `/api/v1`. Schéma OpenAPI : `GET /api/v1/openapi.json` ;
documentation interactive : `/api/docs` (désactivée en production).

## Conventions

- Versionnement dans le chemin (`/api/v1`) ; une rupture de contrat ⇒ `/api/v2`.
- JSON, noms de champs en `snake_case`, dates ISO 8601 UTC.
- Erreurs : format FastAPI standard (`{"detail": ...}`), codes HTTP sémantiques.
- Opérations longues : `202 Accepted` + identifiant de `pipeline_run` à interroger.
- Streaming (voix, réponses du Chief Editor) : WebSocket sous `/api/v1/ws/...` (phase 6/12).
- Authentification : Identity-Aware Proxy devant Cloud Run (usage personnel, compte Google
  unique) ; l'API vérifie l'en-tête signé d'IAP (phase 1, à implémenter avant tout déploiement).

## Endpoints implémentés

| Méthode | Chemin | Description | Réponses |
|---|---|---|---|
| GET | `/api/v1/health` | Vivacité du processus (ne touche aucune dépendance) | 200 |
| GET | `/api/v1/health/ready` | Disponibilité : la base de données répond | 200, 503 |
| POST | `/api/v1/library/imports` | Import d'un lot (multipart `files`, ≤ 200 fichiers ; `?label=`) — traitement asynchrone | 202, 413, 422 |
| GET | `/api/v1/library/imports/{run_id}` | Rapport du lot : statut, durée, totaux, détail par fichier | 200, 404 |
| GET | `/api/v1/library/documents` | Liste (`?status=`, `limit` ≤ 200, `offset`) | 200 |
| GET | `/api/v1/library/documents/{id}` | Détail avec l'état de chaque page | 200, 404 |
| GET | `/api/v1/library/documents/{id}/pages/{n}/image` | Page rendue (`image/webp`) | 200, 404 |

Exemple de réponse d'import :

```json
POST /api/v1/library/imports?label=lot-1  →  202
{"run_id": "…", "items": [
  {"filename": "batman-001.pdf", "outcome": "NEW", "document_id": "…", "error": null},
  {"filename": "notes.txt", "outcome": "REJECTED", "document_id": null,
   "error": "format non reconnu (PDF ou CBZ attendu)"}]}
```

Le nom de fichier envoyé par le client est réduit à son nom de base (aucun chemin n'est accepté).

| Méthode | Chemin | Description | Réponses |
|---|---|---|---|
| POST | `/api/v1/vision/estimates` | Coût estimé d'une analyse (`document_ids`, `provider`, `budget_usd`, `direction`) — ne lance rien | 200, 422 |
| POST | `/api/v1/vision/analyses` | Lance l'analyse si l'estimation tient dans le budget ; sinon 422 avec l'estimation | 202, 422 |
| GET | `/api/v1/vision/analyses/{run_id}` | Rapport : pages réussies/échouées, dépense réelle, jetons, étapes | 200, 404 |
| GET | `/api/v1/library/documents/{id}/pages/{n}/analysis` | Dernière analyse réussie : cases et textes dans l'ordre de lecture, versions et coût | 200, 404 |
| GET | `/api/v1/library/documents/{id}/pages/{n}/panels` | Cases (dernière analyse, sinon détection locale gratuite à la volée) | 200, 404 |
| PUT | `/api/v1/library/documents/{id}/pages/{n}/transcription` | Transcription humaine (`texts[]` : texte, type, case, locuteur, langue) — nouvelle version, coût nul | 201, 404, 422 |
| POST | `/api/v1/transcriptions` | Même opération à URL fixe (`document_id`, `page`, `texts[]` dans le corps) — utilisée par le web | 201, 404, 422 |
| POST | `/api/v1/forensic/analyses` | Exécute les extracteurs (`document_ids` dans l'ordre de lecture, `known_characters`) | 201 |
| GET | `/api/v1/forensic/report?document_ids=…` | Complétude, personnages, contradictions, affirmations, variantes, comptes par type et niveau | 200 |
| GET | `/api/v1/forensic/observations?document_ids=…&kind=&level=&subject=` | Observations courantes avec leurs preuves | 200 |

En mode zéro coût (défaut), `POST /vision/analyses` avec un fournisseur payant renvoie 422.

| Méthode | Chemin | Description | Réponses |
|---|---|---|---|
| POST | `/api/v1/knowledge/build` | Construit entités, relations et index à partir des observations (`document_ids`) | 201 |
| GET | `/api/v1/knowledge/entities?type=&q=` | Entités actives (non fusionnées) | 200 |
| GET | `/api/v1/knowledge/entities/{id}` | Fiche : alias, relations avec preuves, historique des corrections | 200, 404 |
| GET | `/api/v1/knowledge/entities/{id}/graph?depth=1..3` | Voisinage (nœuds, arêtes) | 200, 404 |
| GET | `/api/v1/knowledge/path?from_id=&to_id=` | Plus court chemin | 200, 404 |
| POST | `/api/v1/knowledge/corrections` | `rename`, `add_alias`, `merge`, `retract_relation` — motif obligatoire, journalisé (URL fixe) | 201, 404, 422 |
| POST | `/api/v1/knowledge/relations` | Relation manuelle (preuve obligatoire ; THEORY refusée) | 201, 404, 422 |
| GET | `/api/v1/search?q=&document_ids=` | Recherche hybride (textes servis + entités), scores détaillés | 200, 422 |

Exemple :

```json
GET /api/v1/health/ready
{"status": "ok", "version": "0.1.0", "environment": "staging", "checks": {"database": "ok"}}
```

## Endpoints prévus

| Phase | Ressources |
|---|---|
| 4–5 | `GET /observations`, `GET /entities`, `GET /entities/{id}/relations`, `GET /search?q=` (hybride) |
| 6 | `POST /missions`, `GET /missions/{id}`, `POST /approvals/{id}` |
| 7 | `GET /theories`, `POST /theories/{id}/review` |
| 8 | `GET /market/opportunities?lang=fr` |
| 10 | `POST /scripts`, `GET /scripts/{id}/versions`, `GET /scripts/{id}/score` |
| 12 | `WS /ws/voice` |
| 13 | `GET /integrations/panel-explorer/...`, `GET /integrations/motion-studio/...` (facultatives) |
