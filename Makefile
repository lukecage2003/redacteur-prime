# Raccourcis de développement. Voir DEVELOPMENT.md.
export PRIMESTONE_TEST_DATABASE_URL ?= postgresql+psycopg://primestone:primestone@localhost:5432/primestone_test

.PHONY: install db check test lint typecheck web migrate

install:
	uv sync
	pnpm install

db:
	docker compose up -d db

lint:
	uv run ruff check .
	uv run ruff format --check .
	pnpm --filter @primestone/web lint --max-warnings=0

typecheck:
	uv run mypy
	pnpm --filter @primestone/web typecheck

test:
	uv run pytest
	pnpm --filter @primestone/web test

migrate:
	uv run alembic upgrade head

check: lint typecheck test
