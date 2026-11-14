# ADR-0002 — Stack technique

- Statut : Accepté
- Date : 2026-11-14

## Décision

| Couche | Choix | Raison |
|---|---|---|
| Backend | Python 3.13, FastAPI, Pydantic v2 | écosystème IA/PDF/vision, validation typée, OpenAPI natif, WebSocket |
| Accès BD | SQLAlchemy 2 (Core), psycopg 3, Alembic | SQL explicite (SKIP LOCKED, CTE récursives), migrations versionnées |
| Frontend | Next.js 16, React 19, TypeScript strict, Tailwind 4 | demandé ; App Router ; build autonome pour Cloud Run |
| Qualité | ruff, mypy strict, pytest ; ESLint, tsc, Vitest | rapides, standards |
| Paquets | uv (workspace), pnpm | reproductibles (fichiers de verrouillage) |
| IaC | Terraform — **reporté** | rien à provisionner avant autorisation ; ajouté lors du provisionnement GCP |

## Alternatives considérées

- ORM complet SQLAlchemy : gardé possible module par module ; Core suffit pour la file de tâches.
- Django : plus lourd, moins adapté au streaming asynchrone.
- Poetry : plus lent, moins bon support des workspaces que uv.

## Conséquences

Deux écosystèmes (Python, TypeScript). Les types TypeScript de l'API seront générés depuis
l'OpenAPI (phase 2) pour éviter la dérive des contrats.
