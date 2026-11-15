"""Audience Intelligence : segments (motivations, niveau de connaissance — jamais l'âge),
preuves, liens du graphe d'audience, communauté.

Statut d'un segment, recalculé à chaque preuve : CONFIRMED seulement s'il est soutenu par des
preuves OBSERVÉES actives d'au moins deux natures différentes (METRIC, COMMENT_CLUSTER,
MARKET) ; une déclaration (DECLARED) ne confirme jamais rien.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, Engine, text

from primestone.audience.community import YouTubeComments, classify, insights
from primestone.db.schema import AUDIENCE_KNOWLEDGE_LEVELS

OBSERVED = ("METRIC", "COMMENT_CLUSTER", "MARKET")
FORBIDDEN_DEFINITIONS = ("age", "âge", "ans", "years old", "mineur", "minor")


class AudienceError(ValueError):
    pass


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


class AudienceService:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    # --- Segments -------------------------------------------------------------------------

    def create_segment(
        self,
        *,
        name: str,
        description: str,
        motivations: Sequence[str],
        knowledge_level: str | None,
        author: str,
    ) -> UUID:
        motivations = [m.strip() for m in motivations if m.strip()]
        if not name.strip() or not description.strip() or not motivations:
            raise AudienceError("nom, description et au moins une motivation sont requis")
        if knowledge_level is not None and knowledge_level not in AUDIENCE_KNOWLEDGE_LEVELS:
            raise AudienceError(f"niveau inconnu : {knowledge_level}")
        lowered = f" {name} {' '.join(motivations)} ".lower()
        if any(f" {w} " in lowered for w in FORBIDDEN_DEFINITIONS):
            raise AudienceError("un segment se définit par ses motivations, jamais par l'âge")
        with self._engine.begin() as conn:
            if conn.execute(
                text("SELECT 1 FROM audience_segment WHERE name = :n"), {"n": name}
            ).first():
                raise AudienceError(f"segment déjà défini : {name}")
            segment_id: UUID = conn.execute(
                text(
                    "INSERT INTO audience_segment (name, description, motivations, "
                    "knowledge_level, author) VALUES (:n, :d, CAST(:m AS jsonb), :k, :a) "
                    "RETURNING id"
                ),
                {
                    "n": name.strip(),
                    "d": description.strip(),
                    "m": _json(motivations),
                    "k": knowledge_level,
                    "a": author,
                },
            ).scalar_one()
        return segment_id

    @staticmethod
    def _recompute(conn: Connection, segment_id: UUID) -> str:
        kinds = {
            r[0]
            for r in conn.execute(
                text(
                    "SELECT DISTINCT kind FROM audience_evidence WHERE segment_id = :s "
                    "AND retracted_at IS NULL AND kind = ANY(:k)"
                ),
                {"s": segment_id, "k": list(OBSERVED)},
            ).all()
        }
        status = "CONFIRMED" if len(kinds) >= 2 else "HYPOTHESIS"
        conn.execute(
            text("UPDATE audience_segment SET status = :st, updated_at = now() WHERE id = :s"),
            {"st": status, "s": segment_id},
        )
        return status

    def add_evidence(
        self,
        segment_id: UUID,
        *,
        kind: str,
        statement: str,
        data: dict[str, Any],
        data_class: str,
        author: str,
    ) -> dict[str, str]:
        if kind not in (*OBSERVED, "DECLARED"):
            raise AudienceError(f"nature de preuve inconnue : {kind}")
        if kind in OBSERVED and not data:
            raise AudienceError("une preuve observée doit porter ses données (chiffres, source)")
        if kind == "DECLARED":
            data_class = "HYPOTHESIS"
        with self._engine.begin() as conn:
            if not conn.execute(
                text("SELECT 1 FROM audience_segment WHERE id = :s FOR UPDATE"), {"s": segment_id}
            ).first():
                raise LookupError("segment introuvable")
            evidence_id = conn.execute(
                text(
                    "INSERT INTO audience_evidence (segment_id, kind, statement, data, "
                    "data_class, added_by) VALUES (:s, :k, :st, CAST(:d AS jsonb), :c, :a) "
                    "RETURNING id"
                ),
                {
                    "s": segment_id,
                    "k": kind,
                    "st": statement,
                    "d": _json(data),
                    "c": data_class,
                    "a": author,
                },
            ).scalar_one()
            status = self._recompute(conn, segment_id)
        return {"evidence_id": str(evidence_id), "status": status}

    def retract_evidence(self, evidence_id: UUID) -> str:
        with self._engine.begin() as conn:
            segment_id = conn.execute(
                text(
                    "UPDATE audience_evidence SET retracted_at = now() WHERE id = :e "
                    "AND retracted_at IS NULL RETURNING segment_id"
                ),
                {"e": evidence_id},
            ).scalar_one_or_none()
            if segment_id is None:
                raise LookupError("preuve introuvable ou déjà retirée")
            return self._recompute(conn, segment_id)

    def link(
        self, segment_id: UUID, *, target_kind: str, target: str, relation: str, evidence_id: UUID
    ) -> None:
        """Arête du graphe d'audience : toujours appuyée sur une preuve du MÊME segment."""
        with self._engine.begin() as conn:
            owner = conn.execute(
                text(
                    """
                    SELECT segment_id FROM audience_evidence
                     WHERE id = :e AND retracted_at IS NULL
                    """
                ),
                {"e": evidence_id},
            ).scalar_one_or_none()
            if owner != segment_id:
                raise AudienceError("la preuve doit appartenir à ce segment et être active")
            if (
                target_kind == "ENTITY"
                and not conn.execute(
                    text("SELECT 1 FROM entity WHERE id = CAST(:t AS uuid)"), {"t": target}
                ).first()
            ):
                raise AudienceError("entité inconnue dans le graphe de connaissances")
            conn.execute(
                text(
                    "INSERT INTO audience_link (segment_id, target_kind, target, relation, "
                    "evidence_id) VALUES (:s, :k, :t, :r, :e) ON CONFLICT DO NOTHING"
                ),
                {"s": segment_id, "k": target_kind, "t": target, "r": relation, "e": evidence_id},
            )

    def segments(self) -> list[dict[str, Any]]:
        with self._engine.connect() as conn:
            segments = [
                dict(r)
                for r in conn.execute(
                    text(
                        "SELECT id, name, description, motivations, knowledge_level, status, "
                        + "updated_at "
                        "FROM audience_segment ORDER BY status, name"
                    )
                ).mappings()
            ]
            evidence = (
                conn.execute(
                    text(
                        "SELECT id, segment_id, kind, statement, data, data_class, created_at FROM "
                        "audience_evidence WHERE retracted_at IS NULL ORDER BY created_at"
                    )
                )
                .mappings()
                .all()
            )
            links = (
                conn.execute(
                    text(
                        "SELECT l.segment_id, l.target_kind, l.target, l.relation, "
                        "COALESCE(e.canonical_name, t.name, l.target) AS label "
                        + "FROM audience_link l "
                        "LEFT JOIN entity e ON l.target_kind = 'ENTITY' AND e.id::text = l.target "
                        "LEFT JOIN market_topic t ON l.target_kind = 'TOPIC' "
                        + "AND t.id::text = l.target"
                    )
                )
                .mappings()
                .all()
            )
        for s in segments:
            s["evidence"] = [
                {**dict(e), "id": str(e["id"]), "segment_id": str(e["segment_id"])}
                for e in evidence
                if e["segment_id"] == s["id"]
            ]
            s["links"] = [
                {k: v for k, v in dict(link).items() if k != "segment_id"}
                for link in links
                if link["segment_id"] == s["id"]
            ]
            s["id"] = str(s["id"])
        return segments

    # --- Communauté -----------------------------------------------------------------------

    def import_comments(
        self, comments: Sequence[dict[str, Any]], *, platform: str, content_id: UUID | None = None
    ) -> dict[str, int]:
        stored = 0
        with self._engine.begin() as conn:
            for c in comments:
                body = str(c.get("text") or "").strip()
                if not body or not c.get("external_id"):
                    continue
                published = c.get("published_at")
                if isinstance(published, str):
                    published = datetime.fromisoformat(published.replace("Z", "+00:00"))
                stored += conn.execute(
                    text(
                        "INSERT INTO community_comment (platform, external_id, content_id, text, "
                        "language, kind, like_count, published_at) VALUES "
                        "(:p, :e, :c, :t, :l, :k, :likes, :pub) ON CONFLICT DO NOTHING"
                    ),
                    {
                        "p": platform,
                        "e": str(c["external_id"]),
                        "c": content_id,
                        "t": body[:5000],
                        "l": c.get("language"),
                        "k": classify(body),
                        "likes": int(c.get("like_count") or 0),
                        "pub": published,
                    },
                ).rowcount
        return {"received": len(comments), "stored": stored}

    def collect_youtube(self, client: YouTubeComments, *, max_videos: int = 20) -> dict[str, int]:
        """Commentaires publics des vidéos DE LA CHAÎNE (contenus connus de Primestone)."""
        with self._engine.connect() as conn:
            videos = conn.execute(
                text(
                    "SELECT id, external_id FROM content_item WHERE platform = 'youtube' "
                    "ORDER BY published_at DESC NULLS LAST LIMIT :n"
                ),
                {"n": max_videos},
            ).all()
        stored = 0
        for content_id, video_id in videos:
            stored += self.import_comments(
                client.threads(video_id), platform="youtube", content_id=content_id
            )["stored"]
        return {"videos": len(videos), "stored": stored, "quota_units": client.units}

    def community(self) -> dict[str, Any]:
        with self._engine.connect() as conn:
            comments = [
                dict(r)
                for r in conn.execute(
                    text("SELECT text, kind, like_count FROM community_comment")
                ).mappings()
            ]
            names = [
                r[0]
                for r in conn.execute(
                    text(
                        "SELECT canonical_name FROM entity WHERE merged_into IS NULL "
                        "AND type = 'CHARACTER'"
                    )
                ).all()
            ]
        return insights(comments, names)
