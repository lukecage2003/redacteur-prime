"""Service forensique : exécution des extracteurs, persistance, complétude, rapport.

Gratuit par construction : aucun modèle n'est appelé, seulement des règles sur les
transcriptions existantes (humaines ou issues d'un fournisseur de vision).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import replace
from typing import Any
from uuid import UUID

from sqlalchemy import Engine, text

from primestone.forensic.extract import (
    EXTRACTOR_VERSION,
    ForensicObservation,
    ObservationKind,
    TextRow,
    extract,
)
from primestone.jobs import PostgresJobQueue
from primestone.provenance import BoundingBox, EvidenceLevel, missing_pages

RUN_KIND = "forensic.analyze"

_LATEST = """
    SELECT DISTINCT ON (p.id) p.id AS page_id, p.document_id, p.number, a.id AS analysis_id,
           a.provider
      FROM page p
      JOIN page_analysis a ON a.render_sha256 = p.render_sha256 AND a.status = 'SUCCEEDED'
     WHERE p.document_id = ANY(:ids) AND p.status = 'RENDERED'
     ORDER BY p.id, a.created_at DESC
"""


class ForensicService:
    def __init__(self, engine: Engine, queue: PostgresJobQueue) -> None:
        self._engine = engine
        self._queue = queue

    # --- Entrées ----------------------------------------------------------------------------

    def _latest(self, document_ids: Sequence[UUID]) -> list[dict[str, Any]]:
        with self._engine.connect() as conn:
            return [
                dict(r) for r in conn.execute(text(_LATEST), {"ids": list(document_ids)}).mappings()
            ]

    def text_rows(self, document_ids: Sequence[UUID]) -> list[TextRow]:
        latest = self._latest(document_ids)
        if not latest:
            return []
        by_analysis = {r["analysis_id"]: r for r in latest}
        with self._engine.connect() as conn:
            regions = conn.execute(
                text(
                    'SELECT id, analysis_id, "order", panel_index, kind, text, language, '
                    "confidence, speaker, speaker_confidence, x, y, width, height "
                    "FROM text_region WHERE analysis_id = ANY(:a)"
                ),
                {"a": list(by_analysis)},
            ).mappings()
            rows = []
            for t in regions:
                # Une analyse peut servir plusieurs pages au rendu identique : une ligne par page.
                for page in (r for r in latest if r["analysis_id"] == t["analysis_id"]):
                    rows.append(
                        TextRow(
                            id=t["id"],
                            analysis_id=t["analysis_id"],
                            document_id=page["document_id"],
                            page=page["number"],
                            order=t["order"],
                            panel_index=t["panel_index"],
                            kind=t["kind"],
                            text=t["text"],
                            language=t["language"],
                            confidence=t["confidence"],
                            speaker=t["speaker"],
                            speaker_confidence=t["speaker_confidence"],
                            bbox=BoundingBox(
                                x=t["x"], y=t["y"], width=t["width"], height=t["height"]
                            ),
                            human=page["provider"] == "human",
                        )
                    )
        position = {doc: i for i, doc in enumerate(document_ids)}
        return sorted(rows, key=lambda r: (position.get(r.document_id, 0), r.page, r.order))

    def completeness(self, document_ids: Sequence[UUID]) -> dict[str, dict[str, Any]]:
        """Pages manquantes par document : non rendues, ou rendues mais jamais analysées."""
        analyzed: dict[UUID, set[int]] = defaultdict(set)
        for row in self._latest(document_ids):
            analyzed[row["document_id"]].add(row["number"])
        with self._engine.connect() as conn:
            docs = conn.execute(
                text(
                    "SELECT d.id, d.status, d.page_count, c.expected_page_count, c.title "
                    "FROM document d JOIN comic c ON c.id = d.comic_id WHERE d.id = ANY(:ids)"
                ),
                {"ids": list(document_ids)},
            ).mappings()
            result = {}
            for d in docs:
                expected = d["expected_page_count"] or d["page_count"] or 0
                missing = missing_pages(expected, analyzed[d["id"]])
                result[str(d["id"])] = {
                    "title": d["title"],
                    "document_status": d["status"],
                    "expected_pages": expected,
                    "analyzed_pages": len(analyzed[d["id"]]),
                    "missing_pages": missing,
                    "complete": d["status"] == "COMPLETE" and not missing and expected > 0,
                }
        return result

    # --- Exécution --------------------------------------------------------------------------

    def analyze(
        self, document_ids: Sequence[UUID], known_characters: set[str] | None = None
    ) -> tuple[UUID, dict[str, int]]:
        completeness = self.completeness(document_ids)
        run_id = self._queue.create_run(
            RUN_KIND,
            {
                "document_ids": [str(d) for d in document_ids],
                "extractor": EXTRACTOR_VERSION,
                "known_characters": sorted(known_characters or []),
            },
        )
        observations = extract(self.text_rows(document_ids), known_characters)
        incomplete = {UUID(k) for k, v in completeness.items() if not v["complete"]}
        adjusted = []
        for obs in observations:
            # Une « première apparition » dans un document incomplet n'est qu'une interprétation :
            # une page manquante pourrait contenir une apparition antérieure.
            if obs.kind is ObservationKind.FIRST_APPEARANCE and any(
                e.document_id in incomplete for e in obs.evidence
            ):
                obs = replace(
                    obs,
                    level=EvidenceLevel.INTERPRETATION,
                    statement=obs.statement + " (document incomplet : à confirmer)",
                    confidence=min(obs.confidence, 0.6),
                )
            adjusted.append(obs)
        created = self._persist(run_id, adjusted)
        self._queue.refresh_run(run_id)
        return run_id, {"extracted": len(adjusted), "new": created}

    def _persist(self, run_id: UUID, observations: list[ForensicObservation]) -> int:
        created = 0
        with self._engine.begin() as conn:
            for obs in observations:
                observation_id = conn.execute(
                    text(
                        """
                        INSERT INTO observation (run_id, observation_key, extractor, kind, level,
                               subject, predicate, value, statement, confidence)
                        VALUES (:run, :key, :extractor, :kind, :level, :subject, :predicate,
                                :value, :statement, :confidence)
                        ON CONFLICT (observation_key) DO NOTHING
                        RETURNING id
                        """
                    ),
                    {
                        "run": run_id,
                        "key": obs.key,
                        "extractor": obs.extractor,
                        "kind": obs.kind.value,
                        "level": obs.level.value,
                        "subject": obs.subject,
                        "predicate": obs.predicate,
                        "value": obs.value,
                        "statement": obs.statement,
                        "confidence": max(0.0, min(1.0, obs.confidence)),
                    },
                ).scalar_one_or_none()
                if observation_id is None:
                    continue
                created += 1
                for e in obs.evidence:
                    conn.execute(
                        text(
                            """
                            INSERT INTO evidence_ref (observation_id, document_id, page_number,
                                   panel_index, analysis_id, text_region_id, x, y, width, height,
                                   excerpt, role)
                            VALUES (:obs, :doc, :page, :panel, :analysis, :region, :x, :y, :w,
                                    :h, :excerpt, :role)
                            """
                        ),
                        {
                            "obs": observation_id,
                            "doc": e.document_id,
                            "page": e.page,
                            "panel": e.panel_index,
                            "analysis": e.analysis_id,
                            "region": e.text_region_id,
                            "x": e.bbox.x if e.bbox else None,
                            "y": e.bbox.y if e.bbox else None,
                            "w": e.bbox.width if e.bbox else None,
                            "h": e.bbox.height if e.bbox else None,
                            "excerpt": e.excerpt,
                            "role": e.role.value,
                        },
                    )
        return created

    # --- Lecture ----------------------------------------------------------------------------

    def observations(
        self,
        document_ids: Sequence[UUID],
        *,
        kind: str | None = None,
        level: str | None = None,
        subject: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """Observations COURANTES : toutes leurs preuves viennent des transcriptions servies
        aujourd'hui pour ces documents (une correction humaine rend caduques les anciennes)."""
        current = [r["analysis_id"] for r in self._latest(document_ids)]
        if not current:
            return []
        filters, params = [], {"docs": list(document_ids), "current": current, "limit": limit}
        for column, value in (("kind", kind), ("level", level), ("subject", subject)):
            if value:
                filters.append(f"o.{column} = :{column}")
                params[column] = value
        where = (" AND " + " AND ".join(filters)) if filters else ""
        with self._engine.connect() as conn:
            rows = (
                conn.execute(
                    text(
                        f"""
                        SELECT o.id, o.kind, o.level, o.subject, o.predicate, o.value,
                               o.statement, o.confidence, o.extractor
                          FROM observation o
                         WHERE EXISTS (SELECT 1 FROM evidence_ref e
                                        WHERE e.observation_id = o.id
                                          AND e.document_id = ANY(:docs))
                           AND NOT EXISTS (SELECT 1 FROM evidence_ref e
                                            WHERE e.observation_id = o.id
                                              AND (e.analysis_id <> ALL(:current)
                                                   OR e.document_id <> ALL(:docs))){where}
                         ORDER BY o.kind, o.subject NULLS FIRST, o.statement
                         LIMIT :limit
                        """  # noqa: S608 - colonnes issues d'une liste fixe, valeurs liées
                    ),
                    params,
                )
                .mappings()
                .all()
            )
            ids = [r["id"] for r in rows]
            evidence: dict[UUID, list[dict[str, Any]]] = defaultdict(list)
            if ids:
                for e in conn.execute(
                    text(
                        "SELECT observation_id, document_id, page_number, panel_index, excerpt, "
                        "role FROM evidence_ref WHERE observation_id = ANY(:ids) "
                        "ORDER BY page_number, panel_index NULLS LAST"
                    ),
                    {"ids": ids},
                ).mappings():
                    evidence[e["observation_id"]].append(
                        {
                            "document_id": str(e["document_id"]),
                            "page": e["page_number"],
                            "panel": e["panel_index"],
                            "excerpt": e["excerpt"],
                            "role": e["role"],
                        }
                    )
        return [
            {
                **{k: v for k, v in r.items() if k != "id"},
                "id": str(r["id"]),
                "evidence": evidence[r["id"]],
            }
            for r in rows
        ]

    def report(self, document_ids: Sequence[UUID]) -> dict[str, Any]:
        completeness = self.completeness(document_ids)
        observations = self.observations(document_ids, limit=100_000)
        by_kind_level: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        characters: dict[str, dict[str, Any]] = {}
        for o in observations:
            by_kind_level[o["kind"]][o["level"]] += 1
            if o["kind"] in ("SPEECH", "MENTION", "FIRST_APPEARANCE") and o["subject"]:
                entry = characters.setdefault(
                    o["subject"], {"speeches": 0, "mentions": 0, "first_appearances": []}
                )
                if o["kind"] == "SPEECH":
                    entry["speeches"] += 1
                elif o["kind"] == "MENTION":
                    entry["mentions"] += 1
                else:
                    entry["first_appearances"].append({**o["evidence"][0], "level": o["level"]})
        all_complete = bool(completeness) and all(c["complete"] for c in completeness.values())
        return {
            "status": "COMPLETE" if all_complete else "INCOMPLETE",
            "extractor": EXTRACTOR_VERSION,
            "documents": completeness,
            "observations_by_kind": {k: dict(v) for k, v in sorted(by_kind_level.items())},
            "characters": dict(sorted(characters.items())),
            "contradiction_candidates": [
                o for o in observations if o["kind"] == "CONTRADICTION_CANDIDATE"
            ],
            "alias_candidates": [o for o in observations if o["kind"] == "ALIAS_CANDIDATE"],
            "claims": [o for o in observations if o["kind"] == "CLAIM"],
        }
