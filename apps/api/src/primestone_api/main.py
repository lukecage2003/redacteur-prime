from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import Engine

from primestone import __version__
from primestone.config import Settings, get_settings
from primestone.db import create_db_engine
from primestone_api.routes import health


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings
        app.state.engine = engine or create_db_engine(settings.database_url)
        try:
            yield
        finally:
            if engine is None:
                app.state.engine.dispose()

    app = FastAPI(
        title="PRIMESTONE EDITORIAL API",
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs" if settings.environment != "production" else None,
        openapi_url="/api/v1/openapi.json",
    )
    app.include_router(health.router, prefix="/api/v1")
    return app


app = create_app()
