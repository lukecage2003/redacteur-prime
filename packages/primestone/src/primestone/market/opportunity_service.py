"""Collecte des signaux d'opportunité dans les modules existants (lecture seule)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Engine, text

from primestone.forensic import fold
from primestone.knowledge import Embedder, hybrid_search
from primestone.market.opportunity import METHOD, WEIGHTS, build
from primestone.market.service import MarketService


class OpportunityService:
    def __init__(self, engine: Engine, market: MarketService, embedder: Embedder) -> None:
        self._engine = engine
        self._market = market
        self._embedder = embedder

    def opportunities(self, *, window_days: int = 90, min_items: int = 5) -> dict[str, Any]:
        analysis = self._market.analysis(window_days=window_days, min_items=min_items)
        results = []
        with self._engine.connect() as conn:
            for row in analysis["topics"]:
                topic = (
                    conn.execute(
                        text(
                            """
                            SELECT id, name, keywords_fr, keywords_en
                              FROM market_topic WHERE id = :t
                            """
                        ),
                        {"t": row["topic_id"]},
                    )
                    .mappings()
                    .one()
                )
                keywords = sorted({*topic["keywords_fr"], *topic["keywords_en"]})
                hits = [
                    h
                    for h in hybrid_search(
                        self._engine, self._embedder, " ".join(keywords), limit=40
                    )
                    if h["kind"] == "TEXT" and h["fulltext_rank"] is not None
                ]
                pages = {(h["document_id"], h["page"]) for h in hits}
                patterns = [f"%{fold(k)}%" for k in keywords]
                theories = conn.execute(
                    text(
                        """
                        SELECT count(*) FROM theory t
                         WHERE t.status <> 'REFUTED'
                           AND lower(t.claim || ' ' || t.subjects::text) LIKE ANY(:p)
                        """
                    ),
                    {"p": patterns},
                ).scalar_one()
                kinds: dict[str, int] = {
                    str(k): int(n)
                    for k, n in conn.execute(
                        text(
                            """
                            SELECT kind, count(*) FROM community_comment
                             WHERE translate(lower(text), 'éèêàâîôûùç', 'eeeaaiouuc') LIKE ANY(:p)
                             GROUP BY kind
                            """
                        ),
                        {"p": patterns},
                    ).all()
                }
                measured_community = (
                    conn.execute(text("SELECT count(*) FROM community_comment")).scalar_one() > 0
                )
                segments = [
                    dict(s)
                    for s in conn.execute(
                        text(
                            "SELECT DISTINCT s.name, s.status, s.knowledge_level "
                            "FROM audience_link l "
                            "JOIN audience_segment s ON s.id = l.segment_id "
                            "WHERE l.target_kind = 'TOPIC' AND l.target = :t"
                        ),
                        {"t": row["topic_id"]},
                    ).mappings()
                ]
                fr = row["languages"]["fr"]
                signals = {
                    "gap_score": row.get("gap_score"),
                    "fr_median_views": fr["median_views"],
                    "fr_items": fr["items"],
                    "fr_channels": sorted(
                        {s["channel"] for s in fr["sources"] if s.get("channel")}
                    ),
                    "community_measured": measured_community,
                    "community_requests": kinds.get("REQUEST", 0),
                    "community_questions": kinds.get("QUESTION", 0),
                    "controversies": kinds.get("CONTROVERSY", 0),
                    "pages": len(pages),
                    "examples": [f"« {h['content'][:120]} » (p. {h['page']})" for h in hits[:3]],
                    "theories": theories,
                    "segments": segments,
                }
                results.append(build({"id": row["topic_id"], "name": row["topic"]}, signals))
        results.sort(key=lambda r: (r["status"] != "OPPORTUNITY", -(r["score"] or 0)))
        return {
            "method": METHOD,
            "weights": WEIGHTS,
            "data_class": "ESTIMATE",
            "rule": "Popularité anglophone ≠ demande francophone : sans demande FR observée, "
            "un sujet reste une HYPOTHÈSE.",
            "opportunities": results,
        }
