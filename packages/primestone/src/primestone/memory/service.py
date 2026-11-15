"""Registre des droits, mémoire éditoriale et tableau des coûts.

- Une leçon n'est enregistrée que depuis une preuve OBSERVED (statistiques autorisées en
  base) ou DEMONSTRATED (expérience concluante avec gagnant) : jamais depuis une hypothèse ni
  depuis une sortie non vérifiée d'un agent.
- Les coûts sont lus dans les journaux existants (agents, vision) : aucune estimation inventée.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import Engine, text

from primestone.db.schema import RIGHTS_BASES, RIGHTS_KINDS
from primestone.memory.rights import missing_rights


class MemoryServiceError(ValueError):
    pass


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


class MemoryService:
    def __init__(self, engine: Engine, *, zero_cost: bool = True) -> None:
        self._engine = engine
        self._zero_cost = zero_cost

    # --- Droits -----------------------------------------------------------------------------

    def record_rights(
        self,
        *,
        kind: str,
        subject: str,
        source: str,
        basis: str,
        proof: str,
        limits: str,
        recorded_by: str,
        script_id: UUID | None = None,
        document_title: str | None = None,
        page_number: int | None = None,
        panel_number: int | None = None,
        license: str | None = None,
        expires_on: date | None = None,
    ) -> UUID:
        if kind not in RIGHTS_KINDS or basis not in RIGHTS_BASES:
            raise MemoryServiceError(f"nature : {RIGHTS_KINDS} ; base : {RIGHTS_BASES}")
        if not proof.strip() or not limits.strip() or not source.strip():
            raise MemoryServiceError("source, preuve et limites obligatoires")
        if kind == "PANEL_QUOTE" and (page_number is None or panel_number is None):
            raise MemoryServiceError("une citation de case exige la page et la case")
        if basis == "LICENSE" and not (license or "").strip():
            raise MemoryServiceError("une licence doit être nommée")
        with self._engine.begin() as conn:
            record_id: UUID = conn.execute(
                text(
                    "INSERT INTO rights_record (brand_id, kind, subject, script_id, "
                    "document_title, page_number, panel_number, source, basis, license, proof, "
                    "limits, expires_on, recorded_by) VALUES ((SELECT id FROM media_brand WHERE "
                    "slug = 'primestone'), :kind, :subject, :script, :doc, :page, :panel, "
                    ":source, :basis, :license, :proof, :limits, :expires, :by) RETURNING id"
                ),
                {
                    "kind": kind,
                    "subject": subject,
                    "script": script_id,
                    "doc": document_title,
                    "page": page_number,
                    "panel": panel_number,
                    "source": source,
                    "basis": basis,
                    "license": license,
                    "proof": proof,
                    "limits": limits,
                    "expires": expires_on,
                    "by": recorded_by,
                },
            ).scalar_one()
        return record_id

    def withdraw_rights(self, record_id: UUID) -> None:
        with self._engine.begin() as conn:
            if not conn.execute(
                text(
                    "UPDATE rights_record SET status = 'WITHDRAWN' WHERE id = :id "
                    "AND status = 'ACTIVE' RETURNING id"
                ),
                {"id": record_id},
            ).first():
                raise LookupError("droit actif introuvable")

    def rights(self, script_id: UUID | None = None) -> list[dict[str, Any]]:
        with self._engine.connect() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    text(
                        "SELECT *, (expires_on IS NOT NULL AND expires_on < current_date) "
                        "AS expired FROM rights_record WHERE (CAST(:s AS uuid) IS NULL "
                        "OR script_id = :s OR script_id IS NULL) ORDER BY created_at DESC"
                    ),
                    {"s": script_id},
                ).mappings()
            ]

    def rights_check(self, script_id: UUID) -> dict[str, Any]:
        with self._engine.connect() as conn:
            missing = missing_rights(conn, script_id)
        return {
            "script_id": str(script_id),
            "missing": missing,
            "complete": not missing,
            "rule": "Le registre trace ; il ne juge pas la légalité (décision humaine).",
        }

    # --- Mémoire éditoriale -----------------------------------------------------------------

    def record_lesson(
        self,
        lesson: str,
        *,
        source_type: str,
        source_id: UUID,
        recorded_by: str,
        series_id: UUID | None = None,
    ) -> dict[str, Any]:
        if not lesson.strip():
            raise MemoryServiceError("leçon vide")
        with self._engine.begin() as conn:
            if source_type == "experiment":
                row = (
                    conn.execute(
                        text("SELECT status, result, show_id FROM experiment WHERE id = :id"),
                        {"id": source_id},
                    )
                    .mappings()
                    .one_or_none()
                )
                if row is None:
                    raise LookupError("expérience introuvable")
                result = row["result"] or {}
                if row["status"] != "CONCLUDED" or not result.get("winner"):
                    raise MemoryServiceError(
                        "leçon refusée : l'expérience n'a pas démontré d'effet (pas de gagnant)"
                    )
                level, evidence = "DEMONSTRATED", {"experiment": result}
                series_id = series_id or row["show_id"]
            elif source_type == "content_item":
                metrics = (
                    conn.execute(
                        text(
                            "SELECT metric, value, source, observed_at FROM performance_metric "
                            "WHERE content_id = :id AND dimension IS NULL "
                            "ORDER BY observed_at DESC"
                        ),
                        {"id": source_id},
                    )
                    .mappings()
                    .all()
                )
                if not metrics:
                    raise MemoryServiceError(
                        "leçon refusée : aucune statistique observée pour ce contenu"
                    )
                level = "OBSERVED"
                evidence = {"metrics": [dict(m) for m in metrics[:20]]}
            else:
                raise MemoryServiceError("source possible : content_item ou experiment")
            lesson_id = conn.execute(
                text(
                    "INSERT INTO editorial_lesson (brand_id, series_id, lesson, evidence_level, "
                    "source_type, source_id, evidence, recorded_by) VALUES ((SELECT id FROM "
                    "media_brand WHERE slug = 'primestone'), :s, :l, :e, :t, :sid, "
                    "CAST(:ev AS jsonb), :by) RETURNING id"
                ),
                {
                    "s": series_id,
                    "l": lesson.strip(),
                    "e": level,
                    "t": source_type,
                    "sid": source_id,
                    "ev": _json(evidence),
                    "by": recorded_by,
                },
            ).scalar_one()
        return {"lesson_id": lesson_id, "evidence_level": level}

    def retract_lesson(self, lesson_id: UUID, *, reason: str) -> None:
        if not reason.strip():
            raise MemoryServiceError("un retrait exige un motif")
        with self._engine.begin() as conn:
            if not conn.execute(
                text(
                    "UPDATE editorial_lesson SET status = 'RETRACTED', retracted_reason = :r "
                    "WHERE id = :id AND status = 'ACTIVE' RETURNING id"
                ),
                {"r": reason, "id": lesson_id},
            ).first():
                raise LookupError("leçon active introuvable")

    def lessons(self, series_id: UUID | None = None) -> list[dict[str, Any]]:
        with self._engine.connect() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    text(
                        "SELECT l.*, s.name AS show FROM editorial_lesson l LEFT JOIN series s "
                        "ON s.id = l.series_id WHERE (CAST(:s AS uuid) IS NULL "
                        "OR l.series_id = :s) ORDER BY l.status, l.created_at DESC"
                    ),
                    {"s": series_id},
                ).mappings()
            ]

    def journal(self, limit: int = 100) -> list[dict[str, Any]]:
        """Journal unique : décisions de gouvernance et leçons, du plus récent au plus ancien."""
        with self._engine.connect() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    text(
                        """
                SELECT 'decision' AS kind, id, created_at, action AS title, status,
                       proposed_by AS author FROM editorial_decision
                UNION ALL
                SELECT 'lesson', id, created_at, lesson, evidence_level || ' · ' || status,
                       recorded_by FROM editorial_lesson
                 ORDER BY created_at DESC LIMIT :n
                """
                    ),
                    {"n": limit},
                ).mappings()
            ]

    # --- Coûts et ressources ----------------------------------------------------------------

    def costs(self) -> dict[str, Any]:
        with self._engine.connect() as conn:
            by_mission = [
                dict(r)
                for r in conn.execute(
                    text(
                        """
                SELECT m.id AS mission_id, m.type, m.title, s.name AS show,
                       count(r.id) AS runs, COALESCE(sum(r.cost_usd), 0) AS cost_usd,
                       COALESCE(sum(r.input_tokens + r.output_tokens), 0) AS tokens
                  FROM mission m
                  LEFT JOIN mission_task t ON t.mission_id = m.id
                  LEFT JOIN agent_run r ON r.mission_task_id = t.id
                  LEFT JOIN series s ON s.id = m.show_id
                 GROUP BY m.id, m.type, m.title, s.name
                 ORDER BY cost_usd DESC, m.created_at DESC LIMIT 200
                """
                    )
                ).mappings()
            ]
            by_show = [
                dict(r)
                for r in conn.execute(
                    text(
                        """
                SELECT s.id AS series_id, s.name, count(DISTINCT m.id) AS missions,
                       COALESCE(sum(r.cost_usd), 0) AS cost_usd
                  FROM series s
                  LEFT JOIN mission m ON m.show_id = s.id
                  LEFT JOIN mission_task t ON t.mission_id = m.id
                  LEFT JOIN agent_run r ON r.mission_task_id = t.id
                 GROUP BY s.id, s.name ORDER BY cost_usd DESC, s.name
                """
                    )
                ).mappings()
            ]
            vision = (
                conn.execute(
                    text(
                        "SELECT count(*) AS analyses, COALESCE(sum(cost_usd), 0) AS cost_usd "
                        "FROM page_analysis"
                    )
                )
                .mappings()
                .one()
            )
        total = sum(float(m["cost_usd"]) for m in by_mission) + float(vision["cost_usd"])
        return {
            "zero_cost_mode": self._zero_cost,
            "total_usd": round(total, 6),
            "by_mission": by_mission,
            "by_show": by_show,
            "vision": dict(vision),
            "rule": "Coûts lus dans les journaux (agents, vision) ; aucune estimation inventée.",
        }
