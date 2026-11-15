"""Performance Intelligence : contenus publiés par Primestone, métriques autorisées, boucle
d'apprentissage. Ajout seul : chaque import est un nouvel instantané."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Engine, text

from primestone.db.schema import (
    CONTENT_FORMATS,
    CONTENT_OBJECTIVES,
    EXPERIMENT_VARIABLES,
    PERFORMANCE_METRICS,
)
from primestone.performance.experiments import decide
from primestone.performance.importers import AnalyticsClient, parse_studio_csv
from primestone.performance.learning import learn
from primestone.performance.measurement import evaluate


class PerformanceError(ValueError):
    pass


class PerformanceService:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    @property
    def engine(self) -> Engine:
        return self._engine

    def record(
        self,
        rows: Sequence[dict[str, Any]],
        *,
        source: str,
        author: str,
        platform: str = "youtube",
        period: tuple[Any, Any] = (None, None),
    ) -> dict[str, int]:
        if not author.strip():
            raise PerformanceError("auteur obligatoire")
        contents = metrics = 0
        with self._engine.begin() as conn:
            for row in rows:
                content = conn.execute(
                    text(
                        """
                        INSERT INTO content_item (platform, external_id, title, published_at)
                        VALUES (:p, :e, :t, :pub)
                        ON CONFLICT (platform, external_id) DO UPDATE
                           SET title = CASE WHEN EXCLUDED.title = content_item.external_id
                                            THEN content_item.title ELSE EXCLUDED.title END
                        RETURNING id, (xmax = 0) AS inserted
                        """
                    ),
                    {
                        "p": platform,
                        "e": row["external_id"],
                        "t": row.get("title") or row["external_id"],
                        "pub": row.get("published_on"),
                    },
                ).one()
                contents += 1 if content.inserted else 0
                for metric, value in row["metrics"].items():
                    if metric not in PERFORMANCE_METRICS:
                        raise PerformanceError(f"métrique inconnue : {metric}")
                    conn.execute(
                        text(
                            "INSERT INTO performance_metric (content_id, metric, value, "
                            "period_start, period_end, source, data_class, imported_by, "
                            "dimension, dimension_value) VALUES "
                            "(:c, :m, :v, :ps, :pe, :s, 'PRIVATE_AUTHORIZED', :a, :d, :dv)"
                        ),
                        {
                            "c": content.id,
                            "m": metric,
                            "v": Decimal(value),
                            "ps": period[0],
                            "pe": period[1],
                            "s": source,
                            "a": author,
                            "d": row.get("dimension"),
                            "dv": row.get("dimension_value"),
                        },
                    )
                    metrics += 1
        return {"rows": len(rows), "new_contents": contents, "metrics": metrics}

    def import_studio_csv(
        self, content: str, *, author: str, period: tuple[Any, Any] = (None, None)
    ) -> dict[str, Any]:
        parsed = parse_studio_csv(content)
        result = self.record(
            parsed["rows"], source="YOUTUBE_STUDIO_CSV", author=author, period=period
        )
        return {**result, "ignored_columns": parsed["ignored_columns"]}

    def link_script(self, content_id: UUID, script_id: UUID, *, language: str | None) -> None:
        with self._engine.begin() as conn:
            if not conn.execute(
                text("SELECT 1 FROM script WHERE id = :s"), {"s": script_id}
            ).first():
                raise LookupError("script introuvable")
            updated = conn.execute(
                text(
                    "UPDATE content_item SET script_id = :s, "
                    "language = COALESCE(:l, language) WHERE id = :c"
                ),
                {"s": script_id, "l": language, "c": content_id},
            ).rowcount
        if not updated:
            raise LookupError("contenu introuvable")

    def contents(self) -> list[dict[str, Any]]:
        """Contenus avec la DERNIÈRE valeur de chaque métrique et la note de leur script."""
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT c.id, c.platform, c.external_id, c.title, c.language, c.published_at,
                           c.objective, c.format,
                           c.script_id, s.title AS script_title,
                           (SELECT jsonb_object_agg(metric, value) FROM (
                               SELECT DISTINCT ON (metric) metric, value
                                 FROM performance_metric m
                                WHERE m.content_id = c.id AND m.dimension IS NULL
                                ORDER BY metric, observed_at DESC) last) AS metrics,
                           (SELECT sc.criteria FROM script_score sc
                              JOIN script_version v ON v.id = sc.version_id
                             WHERE v.script_id = c.script_id
                             ORDER BY v.number DESC, sc.created_at DESC LIMIT 1) AS criteria,
                           (SELECT sc.total FROM script_score sc
                              JOIN script_version v ON v.id = sc.version_id
                             WHERE v.script_id = c.script_id
                             ORDER BY v.number DESC, sc.created_at DESC LIMIT 1) AS script_total
                      FROM content_item c LEFT JOIN script s ON s.id = c.script_id
                     ORDER BY c.published_at DESC NULLS LAST, c.title
                    """
                )
            ).mappings()
            return [
                {
                    **dict(r),
                    "id": str(r["id"]),
                    "script_id": str(r["script_id"]) if r["script_id"] else None,
                    "metrics": {k: float(v) for k, v in (r["metrics"] or {}).items()},
                }
                for r in rows
            ]

    def report(self, *, min_items: int = 5) -> dict[str, Any]:
        items = self.contents()
        demonstrated = [
            {
                "title": e["title"],
                "variable": e["variable"],
                "winner": e["result"]["winner"],
                "evidence": "DEMONSTRATED (contexte de l'expérience)",
            }
            for e in self.experiments()
            if e["status"] == "CONCLUDED"
        ]
        return {**self._learn(items, min_items), "demonstrated": demonstrated}

    def _learn(self, items: list[dict[str, Any]], min_items: int) -> dict[str, Any]:
        return learn(
            [
                {
                    "title": c["title"],
                    "metrics": c["metrics"],
                    "script_criteria": {k: v["score"] for k, v in (c["criteria"] or {}).items()}
                    or None,
                }
                for c in items
            ],
            min_items=min_items,
        )

    # --- Phase 14 : objectifs, synchronisation autorisée, expériences ----------------------

    def set_objective(
        self, content_id: UUID, *, objective: str | None, format_: str | None
    ) -> None:
        if objective is not None and objective not in CONTENT_OBJECTIVES:
            raise PerformanceError(f"objectif inconnu : {objective}")
        if format_ is not None and format_ not in CONTENT_FORMATS:
            raise PerformanceError(f"format inconnu : {format_}")
        with self._engine.begin() as conn:
            updated = conn.execute(
                text("UPDATE content_item SET objective = :o, format = :f WHERE id = :c"),
                {"o": objective, "f": format_, "c": content_id},
            ).rowcount
        if not updated:
            raise LookupError("contenu introuvable")

    def objective_report(self) -> dict[str, Any]:
        return evaluate(self.contents())

    def sync_analytics(
        self, client: AnalyticsClient, start: date, end: date, *, author: str, curves: int = 10
    ) -> dict[str, Any]:
        """Statistiques autorisées de la chaîne (API) + courbes de rétention des vidéos."""
        rows = client.video_report(start, end)
        result = self.record(
            rows, source="YOUTUBE_ANALYTICS_API", author=author, period=(start, end)
        )
        stored = 0
        with self._engine.begin() as conn:
            for row in rows[:curves]:
                content_id = conn.execute(
                    text(
                        "SELECT id FROM content_item WHERE platform = 'youtube' "
                        "AND external_id = :e"
                    ),
                    {"e": row["external_id"]},
                ).scalar_one()
                observed = conn.execute(text("SELECT now()")).scalar_one()
                for point in client.retention_curve(row["external_id"], start, end):
                    stored += conn.execute(
                        text(
                            "INSERT INTO retention_point (content_id, elapsed_ratio, "
                            "audience_watch_ratio, relative_performance, source, observed_at) "
                            "VALUES (:c, :e, :w, :r, 'YOUTUBE_ANALYTICS_API', :o) "
                            "ON CONFLICT DO NOTHING"
                        ),
                        {
                            "c": content_id,
                            "o": observed,
                            "e": point["elapsed_ratio"],
                            "w": point["audience_watch_ratio"],
                            "r": point["relative_performance"],
                        },
                    ).rowcount
        return {**result, "retention_points": stored}

    def retention(self, content_id: UUID) -> list[dict[str, float | None]]:
        """Dernière courbe de rétention connue d'un contenu."""
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT elapsed_ratio, audience_watch_ratio, relative_performance
                      FROM retention_point
                     WHERE content_id = :c AND observed_at = (
                           SELECT max(observed_at) FROM retention_point WHERE content_id = :c)
                     ORDER BY elapsed_ratio
                    """
                ),
                {"c": content_id},
            ).all()
        return [
            {
                "elapsed_ratio": float(r[0]),
                "audience_watch_ratio": float(r[1]),
                "relative_performance": float(r[2]) if r[2] is not None else None,
            }
            for r in rows
        ]

    def create_experiment(
        self,
        *,
        title: str,
        hypothesis: str,
        variable: str,
        metric: str,
        author: str,
        audience: str | None = None,
        format_: str | None = None,
        content_ids: Sequence[UUID] = (),
        period: tuple[date | None, date | None] = (None, None),
    ) -> UUID:
        if variable not in EXPERIMENT_VARIABLES:
            raise PerformanceError(f"variable inconnue : {variable}")
        if not title.strip() or not hypothesis.strip() or not metric.strip():
            raise PerformanceError("titre, hypothèse et métrique obligatoires")
        with self._engine.begin() as conn:
            experiment_id: UUID = conn.execute(
                text(
                    "INSERT INTO experiment (title, hypothesis, variable, audience, format, "
                    "metric, content_ids, period_start, period_end, status, author) VALUES "
                    "(:t, :h, :v, :aud, :f, :m, CAST(:c AS jsonb), :ps, :pe, 'RUNNING', :a) "
                    "RETURNING id"
                ),
                {
                    "t": title.strip(),
                    "h": hypothesis.strip(),
                    "v": variable,
                    "aud": audience,
                    "f": format_,
                    "m": metric.strip(),
                    "c": json.dumps([str(c) for c in content_ids]),
                    "ps": period[0],
                    "pe": period[1],
                    "a": author,
                },
            ).scalar_one()
        return experiment_id

    def add_variant(
        self,
        experiment_id: UUID,
        *,
        label: str,
        description: str,
        exposures: int | None = None,
        successes: int | None = None,
        reported_share: Decimal | None = None,
        source: str = "MANUAL",
    ) -> None:
        if (exposures is None) != (successes is None):
            raise PerformanceError("expositions et succès vont ensemble")
        if exposures is None and reported_share is None:
            raise PerformanceError("des comptes ou une part rapportée sont requis")
        with self._engine.begin() as conn:
            status = conn.execute(
                text("SELECT status FROM experiment WHERE id = :e FOR UPDATE"), {"e": experiment_id}
            ).scalar_one_or_none()
            if status is None:
                raise LookupError("expérience introuvable")
            if status in ("CONCLUDED", "INCONCLUSIVE"):
                raise PerformanceError("expérience close : en créer une nouvelle")
            conn.execute(
                text(
                    "INSERT INTO experiment_variant (experiment_id, label, description, "
                    "exposures, successes, reported_share, source) VALUES "
                    "(:e, :l, :d, :n, :s, :r, :src)"
                ),
                {
                    "e": experiment_id,
                    "l": label,
                    "d": description,
                    "n": exposures,
                    "s": successes,
                    "r": reported_share,
                    "src": source,
                },
            )

    def conclude(
        self, experiment_id: UUID, *, conclusion: str | None, next_experiment: str | None
    ) -> dict[str, Any]:
        with self._engine.begin() as conn:
            if not conn.execute(
                text("SELECT 1 FROM experiment WHERE id = :e FOR UPDATE"), {"e": experiment_id}
            ).first():
                raise LookupError("expérience introuvable")
            variants = [
                dict(r)
                for r in conn.execute(
                    text(
                        "SELECT label, exposures, successes, reported_share, source "
                        "FROM experiment_variant WHERE experiment_id = :e ORDER BY label"
                    ),
                    {"e": experiment_id},
                ).mappings()
            ]
            result = decide(variants)
            conn.execute(
                text(
                    "UPDATE experiment SET status = :s, result = CAST(:r AS jsonb), "
                    "conclusion = :c, next_experiment = :n, updated_at = now() WHERE id = :e"
                ),
                {
                    "s": result["status"],
                    "r": json.dumps(result, default=str),
                    "c": conclusion,
                    "n": next_experiment,
                    "e": experiment_id,
                },
            )
        return result

    def experiments(self) -> list[dict[str, Any]]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT id, title, hypothesis, variable, audience, format, metric, status, "
                    "result, conclusion, next_experiment, period_start, period_end, created_at "
                    "FROM experiment ORDER BY created_at DESC"
                )
            ).mappings()
            return [{**dict(r), "id": str(r["id"])} for r in rows]
