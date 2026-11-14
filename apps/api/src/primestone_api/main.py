from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import Engine

from primestone import __version__
from primestone.comic import library_service_from_settings
from primestone.config import Settings, get_settings
from primestone.db import create_db_engine
from primestone.editorial import editorial_service_from_settings
from primestone.forensic import forensic_service
from primestone.knowledge import knowledge_service_from_settings
from primestone.storage import create_object_store
from primestone.vision import vision_service_from_settings
from primestone_api.routes import editorial, forensic, health, knowledge, library, vision


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings
        app.state.engine = engine or create_db_engine(settings.database_url)
        app.state.store = create_object_store(settings.storage_backend, settings.storage_local_root)
        app.state.library = library_service_from_settings(settings, app.state.engine)
        app.state.vision = vision_service_from_settings(settings, app.state.engine)
        app.state.forensic = forensic_service(app.state.engine)
        app.state.knowledge = knowledge_service_from_settings(settings, app.state.engine)
        app.state.editorial = editorial_service_from_settings(settings, app.state.engine)
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
    app.include_router(library.router, prefix="/api/v1")
    app.include_router(vision.router, prefix="/api/v1")
    app.include_router(forensic.router, prefix="/api/v1")
    app.include_router(knowledge.router, prefix="/api/v1")
    app.include_router(editorial.router, prefix="/api/v1")
    return app


app = create_app()
