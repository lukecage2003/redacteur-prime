# DEVELOPMENT

## Prérequis

| Outil | Version | Rôle |
|---|---|---|
| Python | 3.13 (≥ 3.12) | cœur, API, worker |
| uv | ≥ 0.11 | dépendances Python (workspace) |
| Node.js | 22 | web |
| pnpm | 10 (fixé par `packageManager`) | dépendances JS |
| Docker | récent | PostgreSQL + pgvector local, images |

## Installation

```bash
cp .env.example .env
uv sync
pnpm install
docker compose up -d db          # crée aussi la base primestone_test (db/init/)
uv run alembic upgrade head
```

## Lancer

```bash
uv run uvicorn primestone_api.main:app --reload --port 8000   # API → http://localhost:8000/api/docs
uv run primestone-worker                                      # worker
pnpm --filter @primestone/web dev                             # web → http://localhost:3000
docker compose --profile app up --build                      # ou tout en conteneurs
```

## Qualité

```bash
make check     # ruff, ruff format, mypy strict, pytest, eslint, tsc, vitest
```

## Migrations

```bash
uv run alembic revision -m "ajoute la table page"   # puis écrire upgrade/downgrade à la main
uv run alembic upgrade head
uv run alembic check                                 # schéma déclaré = migrations
```

Règles : une migration = un changement cohérent ; `downgrade` toujours écrit ; mettre à jour
`primestone/db/schema.py` et DATA_MODEL.md dans le même commit ; pas d'opération destructive
sans ADR (voir docs/operations/migrations.md).

## Comic Library en local

```bash
uv run primestone-library import ~/Comics --process --workers 4   # import + traitement
uv run primestone-library status <run_id>                         # rapport du lot
```

Sans `--process`, le lot est traité par le worker (`uv run primestone-worker`). Les fichiers
sont stockés sous `PRIMESTONE_STORAGE_LOCAL_ROOT` (défaut `data/storage`, ignoré par Git).

## Ajouter une étape de traitement

1. Écrire un gestionnaire `async def handler(payload) -> dict` idempotent.
2. L'enregistrer : `@registry.register("comic.render_page")`.
3. L'enfiler avec une clé d'idempotence stable.
4. Tester : unitaire (logique) + intégration (file réelle).

## Ajouter un fournisseur IA

Implémenter le protocole `LLMProvider` (`estimate_cost`, `complete`), l'enregistrer dans le
registre, documenter ses conditions dans `docs/operations/ai-providers.md`, et ne jamais l'utiliser
dans la CI. Les tests réels se lancent manuellement, avec budget.
