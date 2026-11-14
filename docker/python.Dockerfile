# Image unique pour l'API et le worker (même code, point d'entrée différent).
#   docker build -f docker/python.Dockerfile --build-arg APP=api .
#   docker build -f docker/python.Dockerfile --build-arg APP=worker .
FROM python:3.15-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY packages/primestone/pyproject.toml packages/primestone/
COPY apps/api/pyproject.toml apps/api/
COPY apps/worker/pyproject.toml apps/worker/
COPY packages/primestone/src packages/primestone/src
COPY apps/api/src apps/api/src
COPY apps/worker/src apps/worker/src
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.15-slim AS runtime
ARG APP=api
ENV PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH" APP=${APP} PORT=8080 \
    PRIMESTONE_STORAGE_LOCAL_ROOT=/data/storage
RUN useradd --system --uid 10001 --no-create-home primestone \
    && mkdir -p /data/storage && chown -R 10001 /data
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY alembic.ini ./
COPY db/migrations db/migrations
USER 10001
EXPOSE 8080
# Cloud Run fournit $PORT. Le worker n'expose pas d'HTTP (Cloud Run worker pool ou Job).
CMD ["sh", "-c", "if [ \"$APP\" = worker ]; then exec primestone-worker; else exec uvicorn primestone_api.main:app --host 0.0.0.0 --port \"$PORT\" --proxy-headers; fi"]
