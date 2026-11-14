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

Exemple :

```json
GET /api/v1/health/ready
{"status": "ok", "version": "0.1.0", "environment": "staging", "checks": {"database": "ok"}}
```

## Endpoints prévus

| Phase | Ressources |
|---|---|
| 2 | `POST /library/imports` (lot), `GET /library/imports/{run_id}`, `GET /comics`, `GET /comics/{id}/pages` |
| 4–5 | `GET /observations`, `GET /entities`, `GET /entities/{id}/relations`, `GET /search?q=` (hybride) |
| 6 | `POST /missions`, `GET /missions/{id}`, `POST /approvals/{id}` |
| 7 | `GET /theories`, `POST /theories/{id}/review` |
| 8 | `GET /market/opportunities?lang=fr` |
| 10 | `POST /scripts`, `GET /scripts/{id}/versions`, `GET /scripts/{id}/score` |
| 12 | `WS /ws/voice` |
| 13 | `GET /integrations/panel-explorer/...`, `GET /integrations/motion-studio/...` (facultatives) |
