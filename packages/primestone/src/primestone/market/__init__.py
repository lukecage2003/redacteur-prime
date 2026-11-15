"""Market Intelligence (phases 2b et 8) : collecte gratuite de données publiques et analyse
transparente des écarts EN→FR. Aucune métrique privée de concurrent."""

from functools import partial

from sqlalchemy import Engine

from primestone.config import Settings
from primestone.market.analysis import METHOD, Item, Topic, analyze, matches
from primestone.market.connectors import (
    ConnectorError,
    YouTubeClient,
    fetch_feed,
    language_of,
    parse_feed,
)
from primestone.market.opportunity import score_topic
from primestone.market.opportunity_service import OpportunityService
from primestone.market.service import MarketError, MarketService

__all__ = [
    "METHOD",
    "ConnectorError",
    "Item",
    "MarketError",
    "MarketService",
    "OpportunityService",
    "Topic",
    "YouTubeClient",
    "analyze",
    "fetch_feed",
    "language_of",
    "market_service_from_settings",
    "matches",
    "opportunity_service_from_settings",
    "parse_feed",
    "score_topic",
]


def market_service_from_settings(settings: Settings, engine: Engine) -> MarketService:
    key = settings.youtube_api_key.get_secret_value() if settings.youtube_api_key else None
    timeout = settings.market_http_timeout_seconds
    return MarketService(
        engine,
        youtube=(lambda: YouTubeClient(key, timeout=timeout)) if key else None,
        youtube_daily_quota=settings.youtube_daily_quota_units,
        fetch_feed=partial(fetch_feed, timeout=timeout),
    )


def opportunity_service_from_settings(settings: Settings, engine: Engine) -> OpportunityService:
    from primestone.knowledge import knowledge_service_from_settings  # dépendance tardive

    return OpportunityService(
        engine,
        market_service_from_settings(settings, engine),
        knowledge_service_from_settings(settings, engine).embedder,
    )
