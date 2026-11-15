"""Canaux, plan de diffusion et portefeuille équilibré.

- Un élément du plan naît PROPOSED ; son approbation est une décision DISTRIBUTION_PLAN.
- Rien ne passe à PUBLISHED sans déclaration humaine (auteur, URL, identifiant public) :
  la plateforme ne publie jamais elle-même (contrainte en base et contrôle du service).
- Le portefeuille compare la répartition du plan à des objectifs par pilier, niveau, langue et
  émission, et signale les déséquilibres sans rien décider.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, Engine, text

from primestone.governance.service import (
    GovernanceError,
    GovernanceService,
    register_handler,
    register_reject_hook,
)
from primestone.shows.service import _require_rights, aggregate

METHOD = "portfolio@1"
DIMENSIONS = ("pillar", "level", "language", "show")
TOLERANCE = 0.15  # écart toléré entre part observée et part visée


class DistributionError(ValueError):
    pass


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _plan(conn: Connection, decision: dict[str, Any], forward: bool) -> dict[str, Any] | None:
    item_id = decision["subject_id"]
    row = (
        conn.execute(
            text(
                "SELECT d.status, d.script_id, s.status AS script_status FROM distribution_item d "
                "LEFT JOIN script s ON s.id = d.script_id WHERE d.id = :id FOR UPDATE OF d"
            ),
            {"id": item_id},
        )
        .mappings()
        .one()
    )
    if forward:
        if row["status"] != "PROPOSED":
            raise GovernanceError(f"élément déjà {row['status']}")
        if row["script_status"] not in (None, "VALIDATED"):
            raise GovernanceError("diffusion refusée : le script n'est pas validé")
        if row["script_id"] is not None:
            _require_rights(conn, row["script_id"])
        target = "APPROVED"
    else:
        if row["status"] == "PUBLISHED":
            raise GovernanceError("élément déjà publié : l'annulation ne peut pas le dépublier")
        target = "CANCELLED"
    conn.execute(
        text("UPDATE distribution_item SET status = :s WHERE id = :id"),
        {"s": target, "id": item_id},
    )
    return {"status": "PROPOSED"} if forward else None


def _plan_rejected(conn: Connection, decision: dict[str, Any]) -> None:
    conn.execute(
        text("UPDATE distribution_item SET status = 'CANCELLED' WHERE id = :id"),
        {"id": decision["subject_id"]},
    )


register_handler("DISTRIBUTION_PLAN", _plan)
register_reject_hook("DISTRIBUTION_PLAN", _plan_rejected)


def balance(
    items: Sequence[Mapping[str, Any]], targets: Mapping[str, Mapping[str, float]]
) -> dict[str, Any]:
    """Part observée de chaque catégorie face à la part visée ; écarts signalés."""
    report: dict[str, Any] = {}
    alerts: list[str] = []
    total = len(items)
    for dimension in DIMENSIONS:
        counts = Counter(str(i.get(dimension) or "non renseigné") for i in items)
        wanted = targets.get(dimension, {})
        rows = []
        for category in sorted(set(counts) | set(wanted)):
            share = counts[category] / total if total else 0.0
            target = wanted.get(category)
            row: dict[str, Any] = {
                "category": category,
                "count": counts[category],
                "share": round(share, 3),
                "target": target,
            }
            if target is not None and abs(share - target) > TOLERANCE:
                row["alert"] = "sous-représenté" if share < target else "sur-représenté"
                alerts.append(
                    f"{dimension} « {category} » : {share:.0%} pour {target:.0%} visés "
                    f"({row['alert']})"
                )
            rows.append(row)
        report[dimension] = rows
    if total == 0:
        alerts.append("plan vide sur la période")
    return {"method": METHOD, "items": total, "dimensions": report, "alerts": alerts}


class DistributionService:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._governance = GovernanceService(engine)

    # --- Canaux -----------------------------------------------------------------------------

    def add_channel(
        self,
        *,
        platform: str,
        language: str,
        handle: str,
        name: str,
        stats_authorization: str = "NONE",
    ) -> UUID:
        if language not in ("fr", "en"):
            raise DistributionError("langues possibles : fr, en")
        with self._engine.begin() as conn:
            if conn.execute(
                text("SELECT 1 FROM distribution_channel WHERE platform = :p AND handle = :h"),
                {"p": platform, "h": handle},
            ).first():
                raise DistributionError(f"canal déjà enregistré : {platform} {handle}")
            channel_id: UUID = conn.execute(
                text(
                    "INSERT INTO distribution_channel (brand_id, platform, language, handle, "
                    "name, stats_authorization) VALUES ((SELECT id FROM media_brand WHERE "
                    "slug = 'primestone'), :p, :l, :h, :n, :a) RETURNING id"
                ),
                {"p": platform, "l": language, "h": handle, "n": name, "a": stats_authorization},
            ).scalar_one()
        return channel_id

    def channels(self) -> list[dict[str, Any]]:
        with self._engine.connect() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    text("SELECT * FROM distribution_channel ORDER BY language, platform, name")
                ).mappings()
            ]

    def set_channel_status(self, channel_id: UUID, status: str) -> None:
        if status not in ("ACTIVE", "PAUSED", "RETIRED"):
            raise DistributionError("statut possible : ACTIVE, PAUSED, RETIRED")
        with self._engine.begin() as conn:
            if not conn.execute(
                text("UPDATE distribution_channel SET status = :s WHERE id = :id RETURNING id"),
                {"s": status, "id": channel_id},
            ).first():
                raise LookupError("canal introuvable")

    # --- Plan de diffusion ------------------------------------------------------------------

    def propose(
        self,
        *,
        channel_id: UUID,
        title: str,
        proposed_by: str,
        script_id: UUID | None = None,
        series_id: UUID | None = None,
        format: str | None = None,
        scheduled_for: datetime | None = None,
    ) -> dict[str, Any]:
        with self._engine.begin() as conn:
            channel = (
                conn.execute(
                    text("SELECT status, language FROM distribution_channel WHERE id = :c"),
                    {"c": channel_id},
                )
                .mappings()
                .one_or_none()
            )
            if channel is None:
                raise LookupError("canal introuvable")
            if channel["status"] != "ACTIVE":
                raise DistributionError(f"canal {channel['status']} : aucune diffusion prévue")
            if script_id is not None:
                script = (
                    conn.execute(
                        text("SELECT language, show_id FROM script WHERE id = :s"),
                        {"s": script_id},
                    )
                    .mappings()
                    .one_or_none()
                )
                if script is None:
                    raise LookupError("script introuvable")
                if script["language"] != channel["language"]:
                    raise DistributionError(
                        "langue du script différente de celle du canal : adapter, pas traduire"
                    )
                series_id = series_id or script["show_id"]
            if series_id is not None:
                status = conn.execute(
                    text("SELECT status FROM series WHERE id = :s"), {"s": series_id}
                ).scalar_one_or_none()
                if status not in ("TESTING", "ACTIVE"):
                    raise DistributionError(f"émission {status} : aucune diffusion prévue")
            item_id = conn.execute(
                text(
                    "INSERT INTO distribution_item (channel_id, script_id, series_id, title, "
                    "format, scheduled_for, created_by) VALUES (:c, :sc, :se, :t, :f, :at, :by) "
                    "RETURNING id"
                ),
                {
                    "c": channel_id,
                    "sc": script_id,
                    "se": series_id,
                    "t": title,
                    "f": format,
                    "at": scheduled_for,
                    "by": proposed_by,
                },
            ).scalar_one()
            decision = self._governance.propose_in(
                conn,
                "DISTRIBUTION_PLAN",
                subject_type="distribution_item",
                subject_id=str(item_id),
                proposal={
                    "title": title,
                    "channel_id": str(channel_id),
                    "scheduled_for": scheduled_for,
                },
                proposed_by=proposed_by,
            )
        return decision | {"item_id": item_id}

    def declare_published(
        self, item_id: UUID, *, url: str, external_id: str, declared_by: str
    ) -> UUID:
        """Déclaration humaine d'une publication faite hors plateforme ; relie les statistiques."""
        if not url.startswith("https://") or not external_id.strip():
            raise DistributionError("déclaration incomplète : URL https et identifiant public")
        with self._engine.begin() as conn:
            item = (
                conn.execute(
                    text(
                        "SELECT d.*, c.platform, c.language FROM distribution_item d "
                        "JOIN distribution_channel c ON c.id = d.channel_id "
                        "WHERE d.id = :id FOR UPDATE OF d"
                    ),
                    {"id": item_id},
                )
                .mappings()
                .one_or_none()
            )
            if item is None:
                raise LookupError("élément du plan introuvable")
            if item["status"] != "APPROVED":
                raise DistributionError("seul un élément approuvé par le fondateur se déclare")
            content_id: UUID = conn.execute(
                text(
                    "INSERT INTO content_item (platform, external_id, title, url, language, "
                    "published_at, script_id, show_id, channel_id, brand_id) VALUES (:p, :e, :t, "
                    ":u, :l, now(), :sc, :se, :c, (SELECT id FROM media_brand WHERE slug = "
                    "'primestone')) ON CONFLICT (platform, external_id) DO UPDATE SET "
                    "url = EXCLUDED.url, channel_id = EXCLUDED.channel_id, "
                    "show_id = COALESCE(content_item.show_id, EXCLUDED.show_id), "
                    "script_id = COALESCE(content_item.script_id, EXCLUDED.script_id) "
                    "RETURNING id"
                ),
                {
                    "p": item["platform"],
                    "e": external_id.strip(),
                    "t": item["title"],
                    "u": url,
                    "l": item["language"],
                    "sc": item["script_id"],
                    "se": item["series_id"],
                    "c": item["channel_id"],
                },
            ).scalar_one()
            conn.execute(
                text(
                    "UPDATE distribution_item SET status = 'PUBLISHED', content_id = :c, "
                    "published_url = :u, declared_by = :by, declared_at = now() WHERE id = :id"
                ),
                {"c": content_id, "u": url, "by": declared_by, "id": item_id},
            )
            if item["script_id"] is not None:
                conn.execute(
                    text(
                        "UPDATE series_episode SET status = 'PUBLISHED', content_id = :c "
                        "WHERE script_id = :s AND status = 'APPROVED'"
                    ),
                    {"c": content_id, "s": item["script_id"]},
                )
        return content_id

    def plan(self, *, start: date | None = None, end: date | None = None) -> list[dict[str, Any]]:
        with self._engine.connect() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    text(
                        """
                SELECT d.id, d.title, d.status, d.format, d.scheduled_for, d.published_url,
                       d.declared_by, d.declared_at, d.script_id, d.series_id, d.content_id,
                       c.platform, c.name AS channel, c.language,
                       sc.level, se.name AS show, p.name AS pillar
                  FROM distribution_item d
                  JOIN distribution_channel c ON c.id = d.channel_id
                  LEFT JOIN script sc ON sc.id = d.script_id
                  LEFT JOIN series se ON se.id = d.series_id
                  LEFT JOIN editorial_pillar p ON p.id = se.pillar_id
                 WHERE (CAST(:a AS date) IS NULL OR
                        COALESCE(d.scheduled_for, d.created_at) >= CAST(:a AS date))
                   AND (CAST(:b AS date) IS NULL OR
                        COALESCE(d.scheduled_for, d.created_at) < CAST(:b AS date) + 1)
                 ORDER BY COALESCE(d.scheduled_for, d.created_at)
                """
                    ),
                    {"a": start, "b": end},
                ).mappings()
            ]

    # --- Portefeuille -----------------------------------------------------------------------

    def create_portfolio(
        self,
        name: str,
        *,
        period_start: date,
        period_end: date,
        targets: dict[str, dict[str, float]],
        created_by: str,
    ) -> UUID:
        unknown = set(targets) - set(DIMENSIONS)
        if unknown:
            raise DistributionError(f"dimensions possibles : {', '.join(DIMENSIONS)}")
        for dimension, shares in targets.items():
            if any(not 0 <= v <= 1 for v in shares.values()) or sum(shares.values()) > 1.0001:
                raise DistributionError(
                    f"parts invalides pour {dimension} (entre 0 et 1, somme ≤ 1)"
                )
        if period_end < period_start:
            raise DistributionError("période incohérente")
        with self._engine.begin() as conn:
            portfolio_id: UUID = conn.execute(
                text(
                    "INSERT INTO content_portfolio (brand_id, name, period_start, period_end, "
                    "targets, created_by) VALUES ((SELECT id FROM media_brand WHERE slug = "
                    "'primestone'), :n, :a, :b, CAST(:t AS jsonb), :by) RETURNING id"
                ),
                {
                    "n": name,
                    "a": period_start,
                    "b": period_end,
                    "t": _json(targets),
                    "by": created_by,
                },
            ).scalar_one()
        return portfolio_id

    def portfolios(self) -> list[dict[str, Any]]:
        with self._engine.connect() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    text("SELECT * FROM content_portfolio ORDER BY period_start DESC")
                ).mappings()
            ]

    def portfolio(self, portfolio_id: UUID) -> dict[str, Any]:
        with self._engine.connect() as conn:
            row = (
                conn.execute(
                    text("SELECT * FROM content_portfolio WHERE id = :id"), {"id": portfolio_id}
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise LookupError("portefeuille introuvable")
        items = [
            i
            for i in self.plan(start=row["period_start"], end=row["period_end"])
            if i["status"] != "CANCELLED"
        ]
        return dict(row) | {"balance": balance(items, row["targets"])}

    # --- Performance par canal --------------------------------------------------------------

    def channel_performance(self) -> list[dict[str, Any]]:
        with self._engine.connect() as conn:
            rows = (
                conn.execute(
                    text(
                        """
                WITH latest AS (
                  SELECT DISTINCT ON (m.content_id, m.metric) m.content_id, m.metric, m.value
                    FROM performance_metric m WHERE m.dimension IS NULL
                   ORDER BY m.content_id, m.metric, m.observed_at DESC
                )
                SELECT ch.id AS channel_id, ch.name, ch.platform, ch.language,
                       ch.stats_authorization,
                       c.id, l.metric, l.value
                  FROM distribution_channel ch
                  LEFT JOIN content_item c ON c.channel_id = ch.id
                  LEFT JOIN latest l ON l.content_id = c.id
                """
                    )
                )
                .mappings()
                .all()
            )
        by_channel: dict[Any, list[Any]] = {}
        for r in rows:
            by_channel.setdefault(r["channel_id"], []).append(r)
        out = []
        for channel_rows in by_channel.values():
            first = channel_rows[0]
            with_content = [r for r in channel_rows if r["id"] is not None]
            summary: dict[str, Any] = {
                k: first[k] for k in ("name", "platform", "language", "stats_authorization")
            } | {"channel_id": str(first["channel_id"])}
            summary["performance"] = (
                aggregate(with_content) if with_content else {"contents": 0, "status": "NON FOURNI"}
            )
            out.append(summary)
        return out
