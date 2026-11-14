"""Recherche hybride gratuite : plein texte PostgreSQL + similarité vectorielle (pgvector),
fusionnées par Reciprocal Rank Fusion. Seuls les textes des transcriptions SERVIES sont
renvoyés (une correction humaine rend les anciennes versions invisibles, sans les effacer)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import Engine, text

from primestone.forensic import fold
from primestone.knowledge.embeddings import Embedder, to_pgvector

RRF_K = 60

_CURRENT = """
    current AS (
        SELECT DISTINCT ON (p.id) a.id AS analysis_id
          FROM page p
          JOIN page_analysis a ON a.render_sha256 = p.render_sha256 AND a.status = 'SUCCEEDED'
         WHERE p.status = 'RENDERED'
           AND (CAST(:docs AS uuid[]) IS NULL OR p.document_id = ANY(:docs))
         ORDER BY p.id, a.created_at DESC
    ),
    visible AS (
        SELECT s.* FROM search_document s
         WHERE s.embedder = :embedder
           AND ((s.kind = 'TEXT'
                 AND (CAST(:docs AS uuid[]) IS NULL OR s.document_id = ANY(:docs))
                 AND EXISTS (SELECT 1 FROM text_region t
                               JOIN current c ON c.analysis_id = t.analysis_id
                              WHERE t.id = s.ref_id))
             OR (s.kind = 'ENTITY'
                 AND EXISTS (SELECT 1 FROM entity e
                              WHERE e.id = s.ref_id AND e.merged_into IS NULL)))
    )
"""


def hybrid_search(
    engine: Engine,
    embedder: Embedder,
    query: str,
    *,
    document_ids: Sequence[UUID] | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    folded = fold(query)
    if not folded:
        return []
    params = {
        "q": folded,
        "vec": to_pgvector(embedder.embed([query])[0]),
        "embedder": embedder.name,
        "docs": list(document_ids) if document_ids else None,
        "pool": max(limit * 3, 30),
    }
    with engine.connect() as conn:
        lexical = conn.execute(
            text(
                f"""
                WITH {_CURRENT}
                SELECT id, ts_rank_cd(to_tsvector('simple', folded),
                                      plainto_tsquery('simple', :q)) AS score
                  FROM visible
                 WHERE to_tsvector('simple', folded) @@ plainto_tsquery('simple', :q)
                 ORDER BY score DESC LIMIT :pool
                """  # noqa: S608 - fragment SQL constant
            ),
            params,
        ).all()
        semantic = conn.execute(
            text(
                f"""
                WITH {_CURRENT}
                SELECT id, 1 - (embedding <=> CAST(:vec AS vector)) AS score
                  FROM visible ORDER BY embedding <=> CAST(:vec AS vector) LIMIT :pool
                """  # noqa: S608 - fragment SQL constant
            ),
            params,
        ).all()
        fused: dict[UUID, float] = {}
        for ranking in (lexical, semantic):
            for rank, (doc_id, _score) in enumerate(ranking, start=1):
                fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (RRF_K + rank)
        top = sorted(fused, key=lambda i: fused[i], reverse=True)[:limit]
        if not top:
            return []
        rows = {
            r["id"]: r
            for r in conn.execute(
                text(
                    "SELECT id, kind, ref_id, document_id, page_number, panel_index, content "
                    "FROM search_document WHERE id = ANY(:ids)"
                ),
                {"ids": top},
            ).mappings()
        }
    lexical_scores: dict[UUID, float] = {row[0]: row[1] for row in lexical}
    semantic_scores: dict[UUID, float] = {row[0]: row[1] for row in semantic}
    return [
        {
            "kind": rows[i]["kind"],
            "ref_id": str(rows[i]["ref_id"]),
            "document_id": str(rows[i]["document_id"]) if rows[i]["document_id"] else None,
            "page": rows[i]["page_number"],
            "panel": rows[i]["panel_index"],
            "content": rows[i]["content"],
            "score": round(fused[i], 6),
            "fulltext_rank": round(float(lexical_scores[i]), 4) if i in lexical_scores else None,
            "vector_similarity": round(float(semantic_scores[i]), 4)
            if i in semantic_scores
            else None,
        }
        for i in top
    ]
