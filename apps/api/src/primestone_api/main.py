from __future__ import annotations

from collections.abc import AsyncIterator, Callable
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
from primestone.lab import lab_from_settings
from primestone.market import market_service_from_settings
from primestone.performance import PerformanceService
from primestone.security import IAPMiddleware, PublicKeys
from primestone.storage import create_object_store
from primestone.storytelling import storytelling_service
from primestone.vision import vision_service_from_settings
from primestone.voice.runtime import VoiceRuntime
from primestone_api.routes import (
    editorial,
    forensic,
    health,
    integrations,
    knowledge,
    lab,
    library,
    market,
    performance,
    scripts,
    vision,
    voice,
)


def create_app(
    settings: Settings | None = None,
    engine: Engine | None = None,
    *,
    iap_keys: Callable[[], PublicKeys] | None = None,
) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings
        app.state.engine = engine or create_db_engine(settings.database_url)
        app.state.store = create_object_store(
            settings.storage_backend, settings.storage_local_root, gcs_bucket=settings.gcs_bucket
        )
        app.state.library = library_service_from_settings(settings, app.state.engine)
        app.state.vision = vision_service_from_settings(settings, app.state.engine)
        app.state.forensic = forensic_service(app.state.engine)
        app.state.knowledge = knowledge_service_from_settings(settings, app.state.engine)
        app.state.editorial = editorial_service_from_settings(settings, app.state.engine)
        app.state.lab = lab_from_settings(settings, app.state.engine)
        app.state.market = market_service_from_settings(settings, app.state.engine)
        app.state.storytelling = storytelling_service(app.state.engine)
        app.state.performance = PerformanceService(app.state.engine)
        app.state.voice = VoiceRuntime(settings, app.state.engine, app.state.knowledge)
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
    if settings.iap_audience:  # obligatoire hors développement (voir Settings)
        app.add_middleware(IAPMiddleware, audience=settings.iap_audience, keys=iap_keys)
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(library.router, prefix="/api/v1")
    app.include_router(vision.router, prefix="/api/v1")
    app.include_router(forensic.router, prefix="/api/v1")
    app.include_router(knowledge.router, prefix="/api/v1")
    app.include_router(editorial.router, prefix="/api/v1")
    app.include_router(lab.router, prefix="/api/v1")
    app.include_router(market.router, prefix="/api/v1")
    app.include_router(scripts.router, prefix="/api/v1")
    app.include_router(performance.router, prefix="/api/v1")
    app.include_router(voice.router, prefix="/api/v1")
    app.include_router(integrations.router, prefix="/api/v1")
    return app


app = create_app()
