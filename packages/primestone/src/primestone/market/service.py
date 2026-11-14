"""Market Intelligence : sources avec fiche, collectes tracées, sujets, analyse.

Règles : aucune collecte depuis une source dont la fiche n'a pas été validée par un humain ;
toute donnée porte sa classe ; seules des métriques publiques sont stockées (contrainte en
base) ; le quota gratuit YouTube n'est jamais dépassé ; rien n'est effacé.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, Engine, text

from primestone.market.analysis import Item, Topic, analyze
from primestone.market.connectors import (
    PUBLIC_METRICS,
    SEARCH_UNITS,
    VIDEOS_UNITS,
    ConnectorError,
    YouTubeClient,
    parse_feed,
)

KINDS = ("YOUTUBE_API", "RSS", "MANUAL")
PRIVATE_METRIC_NAMES = {"ctr", "retention", "impressions", "watch_time", "average_view_duration"}


class MarketError(ValueError):
    pass


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


class MarketService:
    def __init__(
        self,
        engine: Engine,
        *,
        youtube: Callable[[], YouTubeClient] | None = None,
        youtube_daily_quota: int = 10_000,
        fetch_feed: Callable[[str], bytes] | None = None,
    ) -> None:
        self._engine = engine
        self._youtube = youtube
        self._quota = youtube_daily_quota
        self._fetch_feed = fetch_feed

    # --- Sources -------------------------------------------------------------------------------

    def register_source(
        self,
        *,
        key: str,
        name: str,
        kind: str,
        access: str,
        quota: str,
        terms_url: str,
        language: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> UUID:
        if kind not in KINDS:
            raise MarketError(f"type de source inconnu : {kind}")
        if not all(v.strip() for v in (key, name, access, quota, terms_url)):
            raise MarketError("fiche incomplète : clé, nom, accès, quota et conditions requis")
        if kind == "RSS" and not str((config or {}).get("url", "")).startswith("https://"):
            raise MarketError("un flux RSS exige config.url en HTTPS")
        with self._engine.begin() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM market_source WHERE key = :k"), {"k": key}
            ).first()
            if exists:
                raise MarketError(f"source déjà enregistrée : {key}")
            source_id: UUID = conn.execute(
                text(
                    """
                    INSERT INTO market_source (key, name, kind, access, quota, terms_url,
                           data_class, language, config)
                    VALUES (:key, :name, :kind, :access, :quota, :terms, 'PUBLIC', :lang,
                            CAST(:config AS jsonb)) RETURNING id
                    """
                ),
                {
                    "key": key,
                    "name": name,
                    "kind": kind,
                    "access": access,
                    "quota": quota,
                    "terms": terms_url,
                    "lang": language,
                    "config": _json(config or {}),
                },
            ).scalar_one()
        return source_id

    def verify_source(self, key: str, *, author: str) -> None:
        """Validation humaine de la fiche (accès, quotas, conditions relus)."""
        if not author.strip():
            raise MarketError("auteur obligatoire")
        with self._engine.begin() as conn:
            updated = conn.execute(
                text(
                    "UPDATE market_source SET verified_at = now(), verified_by = :a WHERE key = :k"
                ),
                {"a": author, "k": key},
            ).rowcount
        if not updated:
            raise LookupError(f"source inconnue : {key}")

    def sources(self) -> list[dict[str, Any]]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT s.id, s.key, s.name, s.kind, s.access, s.quota, s.terms_url,
                           s.data_class, s.language, s.config, s.verified_at, s.verified_by,
                           (SELECT count(*) FROM market_item i WHERE i.source_id = s.id) AS items,
                           (SELECT max(c.finished_at) FROM market_collection c
                             WHERE c.source_id = s.id AND c.status = 'SUCCEEDED') AS last_collected
                      FROM market_source s ORDER BY s.key
                    """
                )
            ).mappings()
            return [{**dict(r), "id": str(r["id"])} for r in rows]

    def _source(self, conn: Connection, key: str) -> Any:
        row = conn.execute(
            text("SELECT * FROM market_source WHERE key = :k"), {"k": key}
        ).one_or_none()
        if row is None:
            raise LookupError(f"source inconnue : {key}")
        if row.verified_at is None:
            raise MarketError(f"fiche de la source « {key} » non validée : collecte refusée")
        return row

    # --- Collecte ------------------------------------------------------------------------------

    def quota_used_today(self) -> int:
        with self._engine.connect() as conn:
            used: int = conn.execute(
                text(
                    """
                    SELECT COALESCE(sum(c.quota_units), 0) FROM market_collection c
                      JOIN market_source s ON s.id = c.source_id
                     WHERE s.kind = 'YOUTUBE_API'
                       -- le quota YouTube se renouvelle à minuit, heure du Pacifique
                       AND c.started_at >= timezone('America/Los_Angeles',
                               date_trunc('day', timezone('America/Los_Angeles', now())))
                    """
                )
            ).scalar_one()
        return used

    def _store(
        self,
        source: Any,
        records: Sequence[dict[str, Any]],
        *,
        params: dict[str, Any],
        author: str,
        quota_units: int = 0,
        observed_at: datetime | None = None,
    ) -> dict[str, Any]:
        observed_at = observed_at or datetime.now(UTC)
        items = metrics = 0
        with self._engine.begin() as conn:
            collection_id: UUID = conn.execute(
                text(
                    "INSERT INTO market_collection (source_id, status, params, quota_units, author)"
                    " VALUES (:s, 'RUNNING', CAST(:p AS jsonb), :q, :a) RETURNING id"
                ),
                {"s": source.id, "p": _json(params), "q": quota_units, "a": author},
            ).scalar_one()
            for record in records:
                language = record.get("language") or source.language
                if language not in ("fr", "en"):
                    continue  # langue non déterminée : ignoré plutôt que deviné
                item_id = conn.execute(
                    text(
                        """
                        INSERT INTO market_item (source_id, platform, external_id, url, title,
                               description, channel, language, published_at)
                        VALUES (:s, :platform, :ext, :url, :title, :desc, :channel, :lang, :pub)
                        ON CONFLICT (platform, external_id) DO UPDATE
                           SET title = EXCLUDED.title, description = EXCLUDED.description
                        RETURNING id, (xmax = 0) AS inserted
                        """
                    ),
                    {
                        "s": source.id,
                        "platform": record["platform"],
                        "ext": record["external_id"],
                        "url": record.get("url"),
                        "title": record["title"],
                        "desc": record.get("description"),
                        "channel": record.get("channel"),
                        "lang": language,
                        "pub": record.get("published_at"),
                    },
                ).one()
                items += 1 if item_id.inserted else 0
                for metric, value in (record.get("metrics") or {}).items():
                    if metric not in PUBLIC_METRICS:
                        raise MarketError(f"métrique non publique refusée : {metric}")
                    metrics += conn.execute(
                        text(
                            """
                            INSERT INTO market_metric (item_id, collection_id, metric, value,
                                   data_class, observed_at)
                            VALUES (:i, :c, :m, :v, 'PUBLIC', :at)
                            ON CONFLICT (item_id, metric, observed_at) DO NOTHING
                            """
                        ),
                        {
                            "i": item_id.id,
                            "c": collection_id,
                            "m": metric,
                            "v": int(value),
                            "at": record.get("observed_at") or observed_at,
                        },
                    ).rowcount
            conn.execute(
                text(
                    "UPDATE market_collection SET status = 'SUCCEEDED', items = :i, metrics = :m, "
                    "finished_at = now() WHERE id = :c"
                ),
                {"i": items, "m": metrics, "c": collection_id},
            )
        return {
            "collection_id": str(collection_id),
            "records": len(records),
            "new_items": items,
            "metrics": metrics,
            "quota_units": quota_units,
        }

    def _failed(
        self, source: Any, params: dict[str, Any], author: str, error: str, units: int
    ) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO market_collection (source_id, status, params, quota_units, "
                    "author, error, finished_at) VALUES (:s, 'FAILED', CAST(:p AS jsonb), :q, :a, "
                    ":e, now())"
                ),
                {"s": source.id, "p": _json(params), "q": units, "a": author, "e": error},
            )

    def import_records(
        self, source_key: str, records: Sequence[dict[str, Any]], *, author: str
    ) -> dict[str, Any]:
        """Import d'observations publiques relevées à la main (source MANUAL)."""
        normalized = []
        for n, r in enumerate(records, start=1):
            unknown = {k.lower() for k in r} & PRIVATE_METRIC_NAMES
            if unknown:
                raise MarketError(
                    f"ligne {n} : métrique privée refusée ({', '.join(sorted(unknown))})"
                )
            for required in ("platform", "external_id", "title", "observed_at"):
                if not str(r.get(required) or "").strip():
                    raise MarketError(f"ligne {n} : champ « {required} » obligatoire")
            try:
                observed = datetime.fromisoformat(str(r["observed_at"]).replace("Z", "+00:00"))
                published = (
                    datetime.fromisoformat(str(r["published_at"]).replace("Z", "+00:00"))
                    if r.get("published_at")
                    else None
                )
                metrics = {m: int(r[m]) for m in PUBLIC_METRICS if str(r.get(m) or "").strip()}
            except ValueError as exc:
                raise MarketError(f"ligne {n} : valeur invalide ({exc})") from None
            if observed.tzinfo is None or (published and published.tzinfo is None):
                raise MarketError(f"ligne {n} : dates avec fuseau horaire requises")
            if any(v < 0 for v in metrics.values()):
                raise MarketError(f"ligne {n} : valeur négative")
            normalized.append(
                {
                    "platform": str(r["platform"]).strip().lower(),
                    "external_id": str(r["external_id"]).strip(),
                    "url": r.get("url") or None,
                    "title": str(r["title"]).strip(),
                    "description": r.get("description") or None,
                    "channel": r.get("channel") or None,
                    "language": (str(r.get("language") or "").strip().lower() or None),
                    "published_at": published,
                    "observed_at": observed,
                    "metrics": metrics,
                }
            )
        with self._engine.connect() as conn:
            source = self._source(conn, source_key)
        if source.kind != "MANUAL":
            raise MarketError("l'import manuel exige une source de type MANUAL")
        return self._store(source, normalized, params={"import": len(records)}, author=author)

    def collect_rss(self, source_key: str, *, author: str = "collecteur") -> dict[str, Any]:
        with self._engine.connect() as conn:
            source = self._source(conn, source_key)
        if source.kind != "RSS":
            raise MarketError("source non RSS")
        if self._fetch_feed is None:
            raise MarketError("collecte RSS non configurée")
        params = {"url": source.config["url"]}
        try:
            records = parse_feed(
                self._fetch_feed(source.config["url"]), language=source.language or "en"
            )
        except ConnectorError as exc:
            self._failed(source, params, author, str(exc), 0)
            raise MarketError(str(exc)) from None
        return self._store(source, records, params=params, author=author)

    def collect_youtube(
        self,
        source_key: str,
        query: str,
        *,
        language: str,
        max_results: int = 25,
        published_within_days: int | None = 365,
        author: str = "collecteur",
    ) -> dict[str, Any]:
        if language not in ("fr", "en"):
            raise MarketError("langue attendue : fr ou en")
        if not query.strip():
            raise MarketError("requête vide")
        with self._engine.connect() as conn:
            source = self._source(conn, source_key)
        if source.kind != "YOUTUBE_API":
            raise MarketError("source non YouTube")
        if self._youtube is None:
            raise MarketError("YouTube Data API non configurée (PRIMESTONE_YOUTUBE_API_KEY)")
        needed = SEARCH_UNITS + VIDEOS_UNITS
        used = self.quota_used_today()
        if used + needed > self._quota:
            raise MarketError(
                f"quota gratuit du jour atteint ({used}/{self._quota} unités) : réessayer demain"
            )
        params = {"query": query, "language": language, "max_results": max_results}
        client = self._youtube()
        try:
            since = (
                datetime.now(UTC) - timedelta(days=published_within_days)
                if published_within_days
                else None
            )
            records = client.search(
                query, language=language, max_results=max_results, published_after=since
            )
        except ConnectorError as exc:
            self._failed(source, params, author, str(exc), client.units)
            raise MarketError(str(exc)) from None
        finally:
            client.close()
        return self._store(source, records, params=params, author=author, quota_units=client.units)

    def refresh_youtube(
        self, source_key: str, *, author: str = "collecteur", limit: int = 500
    ) -> dict[str, Any]:
        """Nouvel instantané des vues des contenus déjà connus (1 unité pour 50 vidéos)."""
        with self._engine.connect() as conn:
            source = self._source(conn, source_key)
            ids = [
                r[0]
                for r in conn.execute(
                    text(
                        "SELECT external_id FROM market_item WHERE platform = 'youtube' "
                        "ORDER BY first_seen_at DESC LIMIT :n"
                    ),
                    {"n": limit},
                ).all()
            ]
        if self._youtube is None:
            raise MarketError("YouTube Data API non configurée (PRIMESTONE_YOUTUBE_API_KEY)")
        needed = -(-len(ids) // 50) * VIDEOS_UNITS
        if self.quota_used_today() + needed > self._quota:
            raise MarketError("quota gratuit du jour atteint : réessayer demain")
        client = self._youtube()
        try:
            records = client.videos(ids, language=source.language or "en")
        except ConnectorError as exc:
            self._failed(source, {"refresh": len(ids)}, author, str(exc), client.units)
            raise MarketError(str(exc)) from None
        finally:
            client.close()
        return self._store(
            source, records, params={"refresh": len(ids)}, author=author, quota_units=client.units
        )

    def snapshot(self, *, author: str = "collecteur", max_results: int = 25) -> dict[str, Any]:
        """Instantané de toutes les sources validées (à lancer une fois par jour, par cron ou
        Cloud Scheduler). YouTube : une recherche par sujet et par langue, puis rafraîchissement
        des vues ; s'arrête proprement au quota gratuit. Une source en échec n'arrête pas les
        autres."""
        results: dict[str, Any] = {}
        topics = self.topics()
        for source in self.sources():
            if source["verified_at"] is None or source["kind"] == "MANUAL":
                continue
            key = source["key"]
            try:
                if source["kind"] == "RSS":
                    results[key] = self.collect_rss(key, author=author)
                    continue
                runs = []
                for topic in topics:
                    for lang in ("en", "fr"):
                        keywords = topic[f"keywords_{lang}"]
                        if keywords:
                            runs.append(
                                self.collect_youtube(
                                    key,
                                    keywords[0],
                                    language=lang,
                                    max_results=max_results,
                                    author=author,
                                )
                            )
                runs.append(self.refresh_youtube(key, author=author))
                results[key] = runs
            except (MarketError, LookupError) as exc:
                results[key] = {"error": str(exc)}
        return results

    # --- Sujets et analyse ---------------------------------------------------------------------

    def add_topic(
        self, name: str, *, keywords_fr: Sequence[str], keywords_en: Sequence[str], author: str
    ) -> UUID:
        fr = [k.strip() for k in keywords_fr if k.strip()]
        en = [k.strip() for k in keywords_en if k.strip()]
        if not name.strip() or not (fr or en):
            raise MarketError("un sujet exige un nom et au moins un mot-clé")
        with self._engine.begin() as conn:
            if conn.execute(
                text("SELECT 1 FROM market_topic WHERE name = :n"), {"n": name.strip()}
            ).first():
                raise MarketError(f"sujet déjà défini : {name}")
            topic_id: UUID = conn.execute(
                text(
                    "INSERT INTO market_topic (name, keywords_fr, keywords_en, author) VALUES "
                    "(:n, CAST(:fr AS jsonb), CAST(:en AS jsonb), :a) RETURNING id"
                ),
                {"n": name.strip(), "fr": _json(fr), "en": _json(en), "a": author},
            ).scalar_one()
        return topic_id

    def topics(self) -> list[dict[str, Any]]:
        with self._engine.connect() as conn:
            return [
                {**dict(r), "id": str(r["id"])}
                for r in conn.execute(
                    text(
                        "SELECT id, name, keywords_fr, keywords_en, author, created_at "
                        "FROM market_topic ORDER BY name"
                    )
                ).mappings()
            ]

    def _items(self) -> list[Item]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT i.id, i.language, i.title, i.description, i.url, i.channel,
                           i.published_at, i.first_seen_at, v.value AS views, v.observed_at
                      FROM market_item i
                      LEFT JOIN LATERAL (
                          SELECT value, observed_at FROM market_metric m
                           WHERE m.item_id = i.id AND m.metric = 'views'
                           ORDER BY observed_at DESC LIMIT 1) v ON true
                    """
                )
            ).all()
        return [
            Item(
                id=str(r.id),
                language=r.language,
                title=r.title,
                description=r.description,
                url=r.url,
                channel=r.channel,
                published_at=r.published_at,
                first_seen_at=r.first_seen_at,
                views=r.views,
                observed_at=r.observed_at,
            )
            for r in rows
        ]

    def analysis(
        self, *, window_days: int = 90, min_items: int = 5, now: datetime | None = None
    ) -> dict[str, Any]:
        topics = [
            Topic(t["id"], t["name"], tuple(t["keywords_fr"]) + tuple(t["keywords_en"]))
            for t in self.topics()
        ]
        return analyze(
            self._items(),
            topics,
            now=now or datetime.now(UTC),
            window_days=window_days,
            min_items=min_items,
        )

    def collections(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._engine.connect() as conn:
            return [
                {**dict(r), "id": str(r["id"])}
                for r in conn.execute(
                    text(
                        "SELECT c.id, s.key AS source, c.status, c.params, c.items, c.metrics, "
                        "c.quota_units, c.error, c.author, c.started_at, c.finished_at "
                        "FROM market_collection c JOIN market_source s ON s.id = c.source_id "
                        "ORDER BY c.started_at DESC LIMIT :n"
                    ),
                    {"n": limit},
                ).mappings()
            ]
