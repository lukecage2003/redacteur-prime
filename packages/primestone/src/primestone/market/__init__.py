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
from primestone.market.service import MarketError, MarketService

__all__ = [
    "METHOD",
    "ConnectorError",
    "Item",
    "MarketError",
    "MarketService",
    "Topic",
    "YouTubeClient",
    "analyze",
    "fetch_feed",
    "language_of",
    "market_service_from_settings",
    "matches",
    "parse_feed",
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
