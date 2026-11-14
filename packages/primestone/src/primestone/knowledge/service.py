"""Knowledge Intelligence : entités, alias, relations prouvées, corrections, graphe.

Règles :
- les entités et relations sont DÉRIVÉES des observations forensiques (aucun modèle) ;
- toute relation a au moins une preuve (observation et page exactes) ;
- « parle dans un comic » ⇒ APPEARS_IN ; « est nommé dans un comic » ⇒ le comic REFERENCES
  le personnage (être cité n'est pas apparaître) ;
- « X se présente comme Y » ⇒ X REVEALS Y, toujours INTERPRETATION (une affirmation n'est
  pas un fait) ;
- corrections humaines journalisées (`correction`) : renommage, alias, fusion, retrait de
  relation, relation manuelle. Rien n'est effacé : une fusion pointe vers l'entité conservée,
  un retrait date la relation ;
- reconstruire est idempotent et respecte les corrections (fusions et retraits).
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, Engine, text

from primestone.forensic import ForensicService, fold
from primestone.knowledge.embeddings import Embedder, HashingEmbedder, to_pgvector
from primestone.provenance import EvidenceLevel

RUN_KIND = "knowledge.build"
EXTRACTOR = "EXTRACTOR"
HUMAN = "HUMAN"


class KnowledgeError(ValueError):
    pass


@dataclass(frozen=True)
class ManualEvidence:
    document_id: UUID
    page: int
    panel: int | None = None
    excerpt: str | None = None


def _relation_key(
    type_: str, source: UUID, target: UUID, qualifier: str | None, origin: str
) -> str:
    raw = "\x1f".join([type_, str(source), str(target), qualifier or "", origin])
    return hashlib.sha256(raw.encode()).hexdigest()


class KnowledgeService:
    def __init__(
        self, engine: Engine, forensic: ForensicService, embedder: Embedder | None = None
    ) -> None:
        self._engine = engine
        self._forensic = forensic
        self.embedder = embedder or HashingEmbedder()

    # --- Entités -----------------------------------------------------------------------------

    @staticmethod
    def _canonical(conn: Connection, entity_id: UUID) -> UUID:
        merged = conn.execute(
            text("SELECT merged_into FROM entity WHERE id = :id"), {"id": entity_id}
        ).scalar_one()
        return merged or entity_id

    def _resolve(self, conn: Connection, type_: str, name: str, *, key: str | None = None) -> UUID:
        """Entité existante (par alias, fusion suivie) ou nouvelle entité."""
        folded = key or fold(name)
        found = conn.execute(
            text(
                """
                SELECT COALESCE(e.merged_into, e.id)
                  FROM entity_alias a JOIN entity e ON e.id = a.entity_id
                 WHERE a.folded = :folded AND e.type = :type
                 ORDER BY e.created_at LIMIT 1
                """
            ),
            {"folded": folded, "type": type_},
        ).scalar_one_or_none()
        if found is not None:
            return UUID(str(found))
        entity_id: UUID = conn.execute(
            text(
                "INSERT INTO entity (type, canonical_name, folded_name) "
                "VALUES (:type, :name, :folded) RETURNING id"
            ),
            {"type": type_, "name": name, "folded": folded},
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO entity_alias (entity_id, alias, folded, origin) "
                "VALUES (:id, :alias, :folded, 'EXTRACTOR') ON CONFLICT DO NOTHING"
            ),
            {"id": entity_id, "alias": name, "folded": folded},
        )
        return entity_id

    # --- Construction ------------------------------------------------------------------------

    def build(self, document_ids: Sequence[UUID]) -> dict[str, int]:
        observations = self._forensic.observations(document_ids, limit=1_000_000)
        stats = {"entities": 0, "relations": 0, "evidence": 0, "indexed": 0}
        with self._engine.begin() as conn:
            before = conn.execute(text("SELECT count(*) FROM entity")).scalar_one()
            comics = {
                r["document_id"]: r
                for r in conn.execute(
                    text(
                        "SELECT d.id AS document_id, c.id AS comic_id, c.title, c.series_title "
                        "FROM document d JOIN comic c ON c.id = d.comic_id "
                        "WHERE d.id = ANY(:ids)"
                    ),
                    {"ids": list(document_ids)},
                ).mappings()
            }
            comic_entity: dict[UUID, UUID] = {}
            for doc_id, row in comics.items():
                comic_entity[doc_id] = self._resolve(
                    conn, "COMIC", row["title"], key=f"comic:{row['comic_id']}"
                )
                if row["series_title"]:
                    series = self._resolve(conn, "SERIES", row["series_title"])
                    stats["evidence"] += self._link(
                        conn,
                        comic_entity[doc_id],
                        series,
                        "RELATED_TO",
                        "fait partie de la série",
                        [
                            (
                                None,
                                doc_id,
                                1,
                                None,
                                "métadonnées d'import",
                                EvidenceLevel.INTERPRETATION,
                                1.0,
                            )
                        ],
                    )

            # Relations dérivées des observations (preuves = observations courantes).
            pending: dict[tuple[UUID, UUID, str, str | None], list[tuple[Any, ...]]] = defaultdict(
                list
            )
            by_panel: dict[tuple[UUID, int, int | None], list[tuple[UUID, dict[str, Any]]]] = (
                defaultdict(list)
            )
            for obs in observations:
                if not obs["subject"] or not obs["evidence"]:
                    continue
                first = obs["evidence"][0]
                doc_id = UUID(first["document_id"])
                if doc_id not in comic_entity:
                    continue
                level = EvidenceLevel(obs["level"])
                evidence = (
                    UUID(obs["id"]),
                    doc_id,
                    first["page"],
                    first["panel"],
                    first["excerpt"],
                    level,
                    obs["confidence"],
                )
                if obs["kind"] == "SPEECH":
                    character = self._resolve(conn, "CHARACTER", obs["subject"])
                    pending[(character, comic_entity[doc_id], "APPEARS_IN", None)].append(evidence)
                    by_panel[(doc_id, first["page"], first["panel"])].append((character, obs))
                elif obs["kind"] == "MENTION":
                    character = self._resolve(conn, "CHARACTER", obs["subject"])
                    pending[(comic_entity[doc_id], character, "REFERENCES", None)].append(evidence)
                elif obs["kind"] == "CLAIM" and obs["predicate"] == "identity" and obs["value"]:
                    speaker = self._resolve(conn, "CHARACTER", obs["subject"])
                    claimed = self._resolve(conn, "CHARACTER", obs["value"])
                    if speaker != claimed:
                        interpretation = (*evidence[:5], EvidenceLevel.INTERPRETATION, evidence[6])
                        pending[(speaker, claimed, "REVEALS", "se présente comme")].append(
                            interpretation
                        )
            # Co-présence : deux personnages qui parlent dans la même case.
            for speakers in by_panel.values():
                distinct = {c: o for c, o in speakers}
                ids = sorted(distinct, key=str)
                for i, a in enumerate(ids):
                    for b in ids[i + 1 :]:
                        for c in (a, b):
                            o = distinct[c]
                            e = o["evidence"][0]
                            pending[(a, b, "RELATED_TO", "parlent dans la même case")].append(
                                (
                                    UUID(o["id"]),
                                    UUID(e["document_id"]),
                                    e["page"],
                                    e["panel"],
                                    e["excerpt"],
                                    EvidenceLevel.INTERPRETATION,
                                    0.6,
                                )
                            )
            for (source, target, type_, qualifier), evidence_list in pending.items():
                stats["evidence"] += self._link(
                    conn, source, target, type_, qualifier, evidence_list
                )
            stats["entities"] = (
                conn.execute(text("SELECT count(*) FROM entity")).scalar_one() - before
            )
            stats["relations"] = conn.execute(
                text("SELECT count(*) FROM relation WHERE retracted_at IS NULL")
            ).scalar_one()
        stats["indexed"] = self.index(document_ids)
        return stats

    def _link(
        self,
        conn: Connection,
        source: UUID,
        target: UUID,
        type_: str,
        qualifier: str | None,
        evidence: list[tuple[Any, ...]],
    ) -> int:
        source, target = self._canonical(conn, source), self._canonical(conn, target)
        if source == target:
            return 0
        key = _relation_key(type_, source, target, qualifier, EXTRACTOR)
        best = (
            EvidenceLevel.CANON
            if any(e[5] is EvidenceLevel.CANON for e in evidence)
            else EvidenceLevel.INTERPRETATION
        )
        confidence = max(float(e[6]) for e in evidence)
        relation_id = conn.execute(
            text(
                """
                INSERT INTO relation (relation_key, source_id, target_id, type, qualifier, level,
                                      confidence, origin)
                VALUES (:key, :s, :t, :type, :q, :level, :conf, 'EXTRACTOR')
                ON CONFLICT (relation_key) DO UPDATE
                   SET level = CASE WHEN relation.retracted_at IS NULL THEN EXCLUDED.level
                                    ELSE relation.level END,
                       confidence = CASE WHEN relation.retracted_at IS NULL
                                         THEN EXCLUDED.confidence ELSE relation.confidence END,
                       updated_at = now()
                RETURNING id
                """
            ),
            {
                "key": key,
                "s": source,
                "t": target,
                "type": type_,
                "q": qualifier,
                "level": best.value,
                "conf": min(1.0, confidence),
            },
        ).scalar_one()
        added = 0
        for observation_id, doc_id, page, panel, excerpt, _level, _conf in evidence:
            added += conn.execute(
                text(
                    """
                    INSERT INTO relation_evidence (relation_id, observation_id, document_id,
                                                   page_number, panel_index, excerpt)
                    SELECT :r, :o, :d, :p, :panel, :x
                     WHERE NOT EXISTS (SELECT 1 FROM relation_evidence
                                        WHERE relation_id = :r
                                          AND observation_id IS NOT DISTINCT FROM :o
                                          AND document_id = :d AND page_number = :p)
                    """
                ),
                {
                    "r": relation_id,
                    "o": observation_id,
                    "d": doc_id,
                    "p": page,
                    "panel": panel,
                    "x": excerpt,
                },
            ).rowcount
        return added

    # --- Index de recherche -------------------------------------------------------------------

    def index(self, document_ids: Sequence[UUID]) -> int:
        rows = self._forensic.text_rows(document_ids)
        texts = [(r.id, r.document_id, r.page, r.panel_index, r.text) for r in rows]
        with self._engine.connect() as conn:
            entities = conn.execute(
                text(
                    """
                    SELECT e.id,
                           trim(e.canonical_name || ' ' || COALESCE(string_agg(
                               DISTINCT a.alias, ' ') FILTER (WHERE a.folded <> e.folded_name
                                                         AND a.alias <> e.canonical_name), ''))
                               AS content
                      FROM entity e
                      LEFT JOIN entity a_e ON a_e.id = e.id OR a_e.merged_into = e.id
                      LEFT JOIN entity_alias a ON a.entity_id = a_e.id
                     WHERE e.merged_into IS NULL
                     GROUP BY e.id
                    """
                )
            ).all()
        items = [("TEXT", *t) for t in texts] + [
            ("ENTITY", e[0], None, None, None, e[1]) for e in entities
        ]
        if not items:
            return 0
        vectors = self.embedder.embed([i[5] for i in items])
        with self._engine.begin() as conn:
            for (kind, ref, doc, page, panel, content), vector in zip(items, vectors, strict=True):
                conn.execute(
                    text(
                        """
                        INSERT INTO search_document (kind, ref_id, document_id, page_number,
                               panel_index, content, folded, embedder, embedding)
                        VALUES (:kind, :ref, :doc, :page, :panel, :content, :folded, :embedder,
                                CAST(:vec AS vector))
                        ON CONFLICT (kind, ref_id, embedder) DO UPDATE
                           SET content = EXCLUDED.content, folded = EXCLUDED.folded,
                               embedding = EXCLUDED.embedding
                        """
                    ),
                    {
                        "kind": kind,
                        "ref": ref,
                        "doc": doc,
                        "page": page,
                        "panel": panel,
                        "content": content,
                        "folded": fold(content),
                        "embedder": self.embedder.name,
                        "vec": to_pgvector(vector),
                    },
                )
        return len(items)

    # --- Corrections humaines (journalisées) --------------------------------------------------

    @staticmethod
    def _log(
        conn: Connection,
        target_type: str,
        target_id: UUID,
        action: str,
        before: Any,
        after: Any,
        author: str,
        reason: str,
    ) -> None:
        if not reason.strip():
            raise KnowledgeError("une correction doit être motivée")
        conn.execute(
            text(
                "INSERT INTO correction (target_type, target_id, action, before, after, author, "
                "reason) VALUES (:t, :id, :a, CAST(:b AS jsonb), CAST(:af AS jsonb), :au, :r)"
            ),
            {
                "t": target_type,
                "id": target_id,
                "a": action,
                "b": json.dumps(before, default=str),
                "af": json.dumps(after, default=str),
                "au": author,
                "r": reason,
            },
        )

    def _entity_row(self, conn: Connection, entity_id: UUID) -> dict[str, Any]:
        row = (
            conn.execute(
                text(
                    "SELECT id, type, canonical_name, description, merged_into FROM entity "
                    "WHERE id = :id"
                ),
                {"id": entity_id},
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise LookupError("entité introuvable")
        return dict(row)

    def rename(self, entity_id: UUID, name: str, *, author: str, reason: str) -> None:
        with self._engine.begin() as conn:
            before = self._entity_row(conn, entity_id)
            conn.execute(
                text("UPDATE entity SET canonical_name = :n, updated_at = now() WHERE id = :id"),
                {"n": name, "id": entity_id},
            )
            conn.execute(
                text(
                    "INSERT INTO entity_alias (entity_id, alias, folded, origin) "
                    "VALUES (:id, :a, :f, 'HUMAN') ON CONFLICT DO NOTHING"
                ),
                {"id": entity_id, "a": name, "f": fold(name)},
            )
            self._log(
                conn,
                "ENTITY",
                entity_id,
                "RENAME",
                {"canonical_name": before["canonical_name"]},
                {"canonical_name": name},
                author,
                reason,
            )

    def add_alias(
        self, entity_id: UUID, alias: str, *, language: str | None, author: str, reason: str
    ) -> None:
        with self._engine.begin() as conn:
            entity = self._entity_row(conn, entity_id)
            clash = conn.execute(
                text(
                    "SELECT COALESCE(e.merged_into, e.id) FROM entity_alias a "
                    "JOIN entity e ON e.id = a.entity_id WHERE a.folded = :f AND e.type = :t"
                ),
                {"f": fold(alias), "t": entity["type"]},
            ).scalar_one_or_none()
            if clash is not None and clash != entity_id:
                raise KnowledgeError("alias déjà porté par une autre entité : fusionner plutôt")
            conn.execute(
                text(
                    "INSERT INTO entity_alias (entity_id, alias, folded, language, origin) "
                    "VALUES (:id, :a, :f, :l, 'HUMAN') ON CONFLICT DO NOTHING"
                ),
                {"id": entity_id, "a": alias, "f": fold(alias), "l": language},
            )
            self._log(
                conn,
                "ENTITY",
                entity_id,
                "ADD_ALIAS",
                None,
                {"alias": alias, "language": language},
                author,
                reason,
            )

    def merge(self, keep_id: UUID, absorb_id: UUID, *, author: str, reason: str) -> None:
        if keep_id == absorb_id:
            raise KnowledgeError("impossible de fusionner une entité avec elle-même")
        with self._engine.begin() as conn:
            keep, absorb = self._entity_row(conn, keep_id), self._entity_row(conn, absorb_id)
            if keep["merged_into"] or absorb["merged_into"]:
                raise KnowledgeError("entité déjà fusionnée")
            if keep["type"] != absorb["type"]:
                raise KnowledgeError("types différents")
            # Aplatissement : ce qui pointait vers l'absorbée pointe désormais vers la conservée.
            conn.execute(
                text(
                    "UPDATE entity SET merged_into = :k, updated_at = now() "
                    "WHERE id = :a OR merged_into = :a"
                ),
                {"k": keep_id, "a": absorb_id},
            )
            self._log(
                conn,
                "ENTITY",
                absorb_id,
                "MERGE",
                {"merged_into": None},
                {
                    "merged_into": keep_id,
                    "kept": keep["canonical_name"],
                    "absorbed": absorb["canonical_name"],
                },
                author,
                reason,
            )

    def retract_relation(self, relation_id: UUID, *, author: str, reason: str) -> None:
        with self._engine.begin() as conn:
            row = conn.execute(
                text("SELECT retracted_at FROM relation WHERE id = :id FOR UPDATE"),
                {"id": relation_id},
            ).one_or_none()
            if row is None:
                raise LookupError("relation introuvable")
            if row[0] is not None:
                raise KnowledgeError("relation déjà retirée")
            conn.execute(
                text("UPDATE relation SET retracted_at = now(), updated_at = now() WHERE id = :id"),
                {"id": relation_id},
            )
            self._log(
                conn,
                "RELATION",
                relation_id,
                "RETRACT",
                {"retracted": False},
                {"retracted": True},
                author,
                reason,
            )

    def create_relation(
        self,
        source_id: UUID,
        target_id: UUID,
        type_: str,
        *,
        qualifier: str | None,
        level: EvidenceLevel,
        evidence: Sequence[ManualEvidence],
        author: str,
        reason: str,
    ) -> UUID:
        if not evidence:
            raise KnowledgeError("une relation sans preuve est interdite")
        if level is EvidenceLevel.THEORY:
            raise KnowledgeError("les théories relèvent du laboratoire (phase 7)")
        with self._engine.begin() as conn:
            source = self._canonical(conn, self._entity_row(conn, source_id)["id"])
            target = self._canonical(conn, self._entity_row(conn, target_id)["id"])
            if source == target:
                raise KnowledgeError("une relation relie deux entités distinctes")
            for e in evidence:
                exists = conn.execute(
                    text("SELECT 1 FROM page WHERE document_id = :d AND number = :p"),
                    {"d": e.document_id, "p": e.page},
                ).scalar_one_or_none()
                if exists is None:
                    raise KnowledgeError(f"preuve invalide : page {e.page} introuvable")
            key = _relation_key(type_, source, target, qualifier, HUMAN)
            relation_id = conn.execute(
                text(
                    """
                    INSERT INTO relation (relation_key, source_id, target_id, type, qualifier,
                                          level, confidence, origin)
                    VALUES (:key, :s, :t, :type, :q, :level, 1.0, 'HUMAN')
                    ON CONFLICT (relation_key) DO NOTHING RETURNING id
                    """
                ),
                {
                    "key": key,
                    "s": source,
                    "t": target,
                    "type": type_,
                    "q": qualifier,
                    "level": level.value,
                },
            ).scalar_one_or_none()
            if relation_id is None:
                raise KnowledgeError("relation identique déjà enregistrée")
            for e in evidence:
                conn.execute(
                    text(
                        "INSERT INTO relation_evidence (relation_id, document_id, page_number, "
                        "panel_index, excerpt) VALUES (:r, :d, :p, :panel, :x)"
                    ),
                    {
                        "r": relation_id,
                        "d": e.document_id,
                        "p": e.page,
                        "panel": e.panel,
                        "x": e.excerpt,
                    },
                )
            self._log(
                conn,
                "RELATION",
                relation_id,
                "CREATE",
                None,
                {"type": type_, "qualifier": qualifier, "level": level.value},
                author,
                reason,
            )
        return UUID(str(relation_id))

    # --- Lecture -----------------------------------------------------------------------------

    def entities(
        self, *, type_: str | None = None, query: str | None = None, limit: int = 200
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit}
        where = ["e.merged_into IS NULL"]
        if type_:
            where.append("e.type = :type")
            params["type"] = type_
        if query:
            where.append(
                "EXISTS (SELECT 1 FROM entity_alias a WHERE a.entity_id = e.id "
                "AND a.folded LIKE :q)"
            )
            params["q"] = f"%{fold(query)}%"
        with self._engine.connect() as conn:
            rows = (
                conn.execute(
                    text(
                        f"""
                    SELECT e.id, e.type, e.canonical_name,
                           (SELECT count(*) FROM relation r
                             WHERE r.retracted_at IS NULL
                               AND (r.source_id = e.id OR r.target_id = e.id)) AS relations
                      FROM entity e WHERE {" AND ".join(where)}
                     ORDER BY e.type, e.canonical_name LIMIT :limit
                    """  # noqa: S608 - fragments fixes, valeurs liées
                    ),
                    params,
                )
                .mappings()
                .all()
            )
        return [{**dict(r), "id": str(r["id"])} for r in rows]

    def entity(self, entity_id: UUID) -> dict[str, Any] | None:
        with self._engine.connect() as conn:
            row = (
                conn.execute(
                    text(
                        "SELECT id, type, canonical_name, description, merged_into FROM entity "
                        "WHERE id = :id"
                    ),
                    {"id": entity_id},
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                return None
            if row["merged_into"]:
                return {"id": str(row["id"]), "merged_into": str(row["merged_into"])}
            aliases = (
                conn.execute(
                    text(
                        "SELECT a.alias, a.language, a.origin FROM entity_alias a JOIN entity e "
                        "ON e.id = a.entity_id WHERE e.id = :id OR e.merged_into = :id "
                        "ORDER BY a.alias"
                    ),
                    {"id": entity_id},
                )
                .mappings()
                .all()
            )
            relations = (
                conn.execute(
                    text(
                        """
                    SELECT r.id, r.type, r.qualifier, r.level, r.confidence, r.origin,
                           r.retracted_at, r.source_id, r.target_id,
                           s.canonical_name AS source_name, t.canonical_name AS target_name
                      FROM relation r
                      JOIN entity s ON s.id = r.source_id
                      JOIN entity t ON t.id = r.target_id
                     WHERE r.source_id IN (SELECT id FROM entity
                                            WHERE id = :id OR merged_into = :id)
                        OR r.target_id IN (SELECT id FROM entity
                                            WHERE id = :id OR merged_into = :id)
                     ORDER BY r.retracted_at NULLS FIRST, r.type, r.level
                    """
                    ),
                    {"id": entity_id},
                )
                .mappings()
                .all()
            )
            evidence: dict[UUID, list[dict[str, Any]]] = defaultdict(list)
            ids = [r["id"] for r in relations]
            if ids:
                for e in conn.execute(
                    text(
                        "SELECT relation_id, document_id, page_number, panel_index, excerpt "
                        "FROM relation_evidence WHERE relation_id = ANY(:ids) "
                        "ORDER BY page_number"
                    ),
                    {"ids": ids},
                ).mappings():
                    evidence[e["relation_id"]].append(
                        {
                            "document_id": str(e["document_id"]),
                            "page": e["page_number"],
                            "panel": e["panel_index"],
                            "excerpt": e["excerpt"],
                        }
                    )
            history = (
                conn.execute(
                    text(
                        "SELECT action, before, after, author, reason, created_at FROM correction "
                        "WHERE target_id = :id "
                        "OR target_id IN (SELECT id FROM entity WHERE merged_into = :id) "
                        "ORDER BY created_at"
                    ),
                    {"id": entity_id},
                )
                .mappings()
                .all()
            )
        return {
            "id": str(row["id"]),
            "type": row["type"],
            "canonical_name": row["canonical_name"],
            "description": row["description"],
            "aliases": [dict(a) for a in aliases],
            "relations": [
                {
                    "id": str(r["id"]),
                    "type": r["type"],
                    "qualifier": r["qualifier"],
                    "level": r["level"],
                    "confidence": r["confidence"],
                    "origin": r["origin"],
                    "retracted": r["retracted_at"] is not None,
                    "source": {"id": str(r["source_id"]), "name": r["source_name"]},
                    "target": {"id": str(r["target_id"]), "name": r["target_name"]},
                    "evidence": evidence[r["id"]],
                }
                for r in relations
            ],
            "history": [{**dict(h), "created_at": h["created_at"].isoformat()} for h in history],
        }

    _EDGES = """
        edges AS (
            SELECT COALESCE(s.merged_into, s.id) AS a, COALESCE(t.merged_into, t.id) AS b,
                   r.id AS relation_id, r.type, r.level
              FROM relation r
              JOIN entity s ON s.id = r.source_id
              JOIN entity t ON t.id = r.target_id
             WHERE r.retracted_at IS NULL
        ),
        undirected AS (
            SELECT a, b, relation_id, type, level FROM edges
            UNION ALL SELECT b, a, relation_id, type, level FROM edges
        )
    """

    def neighbors(self, entity_id: UUID, depth: int = 1) -> dict[str, Any]:
        """Voisinage (graphe non orienté, relations actives, fusions résolues) — CTE récursive."""
        depth = max(1, min(depth, 3))
        with self._engine.connect() as conn:
            root = self._canonical(conn, self._entity_row(conn, entity_id)["id"])
            nodes = (
                conn.execute(
                    text(
                        f"""
                    WITH RECURSIVE {self._EDGES},
                    walk(id, distance) AS (
                        SELECT CAST(:root AS uuid), 0
                        UNION
                        SELECT u.b, w.distance + 1 FROM walk w JOIN undirected u ON u.a = w.id
                         WHERE w.distance < :depth
                    )
                    SELECT w.id, min(w.distance) AS distance, e.type, e.canonical_name
                      FROM walk w JOIN entity e ON e.id = w.id
                     GROUP BY w.id, e.type, e.canonical_name ORDER BY distance, e.canonical_name
                    """  # noqa: S608 - fragment SQL constant
                    ),
                    {"root": root, "depth": depth},
                )
                .mappings()
                .all()
            )
            ids = [n["id"] for n in nodes]
            edges = (
                conn.execute(
                    text(
                        f"""
                    WITH {self._EDGES}
                    SELECT DISTINCT relation_id, a, b, type, level FROM edges
                     WHERE a = ANY(:ids) AND b = ANY(:ids)
                    """  # noqa: S608 - fragment SQL constant
                    ),
                    {"ids": ids},
                )
                .mappings()
                .all()
            )
        return {
            "root": str(root),
            "nodes": [
                {
                    "id": str(n["id"]),
                    "distance": n["distance"],
                    "type": n["type"],
                    "name": n["canonical_name"],
                }
                for n in nodes
            ],
            "edges": [
                {
                    "relation_id": str(e["relation_id"]),
                    "source": str(e["a"]),
                    "target": str(e["b"]),
                    "type": e["type"],
                    "level": e["level"],
                }
                for e in edges
            ],
        }

    def path(self, from_id: UUID, to_id: UUID, max_depth: int = 4) -> list[dict[str, Any]] | None:
        """Plus court chemin (en nombre de relations) entre deux entités, ou None."""
        max_depth = max(1, min(max_depth, 6))
        with self._engine.connect() as conn:
            start = self._canonical(conn, self._entity_row(conn, from_id)["id"])
            goal = self._canonical(conn, self._entity_row(conn, to_id)["id"])
            row = conn.execute(
                text(
                    f"""
                    WITH RECURSIVE {self._EDGES},
                    bfs(node, nodes, relations, depth) AS (
                        SELECT CAST(:start AS uuid), ARRAY[CAST(:start AS uuid)],
                               ARRAY[]::uuid[], 0
                        UNION ALL
                        SELECT u.b, b.nodes || u.b, b.relations || u.relation_id, b.depth + 1
                          FROM bfs b JOIN undirected u ON u.a = b.node
                         WHERE b.depth < :max AND NOT u.b = ANY(b.nodes)
                    )
                    SELECT nodes, relations FROM bfs WHERE node = :goal
                     ORDER BY depth LIMIT 1
                    """  # noqa: S608 - fragment SQL constant
                ),
                {"start": start, "goal": goal, "max": max_depth},
            ).one_or_none()
            if row is None:
                return None
            nodes, relation_ids = row
            names: dict[UUID, str] = dict(
                conn.execute(
                    text("SELECT id, canonical_name FROM entity WHERE id = ANY(:ids)"),
                    {"ids": list(nodes)},
                ).all()
            )
            rels = {
                r["id"]: r
                for r in conn.execute(
                    text("SELECT id, type, qualifier, level FROM relation WHERE id = ANY(:ids)"),
                    {"ids": list(relation_ids)},
                ).mappings()
            }
        steps: list[dict[str, Any]] = []
        for i, node in enumerate(nodes):
            step: dict[str, Any] = {"entity": {"id": str(node), "name": names[node]}}
            if i > 0:
                r = rels[relation_ids[i - 1]]
                step["via"] = {
                    "relation_id": str(r["id"]),
                    "type": r["type"],
                    "qualifier": r["qualifier"],
                    "level": r["level"],
                }
            steps.append(step)
        return steps
