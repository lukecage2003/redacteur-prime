"""Performance Intelligence : contenus publiés par Primestone, métriques autorisées, boucle
d'apprentissage. Ajout seul : chaque import est un nouvel instantané."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Engine, text

from primestone.db.schema import PERFORMANCE_METRICS
from primestone.performance.importers import parse_studio_csv
from primestone.performance.learning import learn


class PerformanceError(ValueError):
    pass


class PerformanceService:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

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
                            "period_start, period_end, source, data_class, imported_by) VALUES "
                            "(:c, :m, :v, :ps, :pe, :s, 'PRIVATE_AUTHORIZED', :a)"
                        ),
                        {
                            "c": content.id,
                            "m": metric,
                            "v": Decimal(value),
                            "ps": period[0],
                            "pe": period[1],
                            "s": source,
                            "a": author,
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
                           c.script_id, s.title AS script_title,
                           (SELECT jsonb_object_agg(metric, value) FROM (
                               SELECT DISTINCT ON (metric) metric, value
                                 FROM performance_metric m WHERE m.content_id = c.id
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
