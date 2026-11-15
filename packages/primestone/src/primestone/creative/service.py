"""Creative Intelligence : charte versionnée, séries et franchises, packaging par script."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Sequence
from statistics import mean
from typing import Any
from uuid import UUID

from sqlalchemy import Engine, text

from primestone.creative.brand import DEFAULT_CHARTER
from primestone.creative.packaging import METHOD, build
from primestone.forensic import fold
from primestone.governance.service import GovernanceService
from primestone.shows.service import ShowService

TitleWriter = Callable[[str, str], Awaitable[list[str]]]


class CreativeError(ValueError):
    pass


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


class CreativeService:
    def __init__(self, engine: Engine, title_writer: TitleWriter | None = None) -> None:
        self._engine = engine
        self._title_writer = title_writer

    # --- Charte -------------------------------------------------------------------------

    def charter(self) -> dict[str, Any]:
        with self._engine.connect() as conn:
            row = (
                conn.execute(
                    text(
                        "SELECT version, name, rules, author, note, status, approved_by, "
                        "approved_at, created_at FROM brand_charter WHERE status = 'APPROVED' "
                        "ORDER BY version DESC LIMIT 1"
                    )
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            return {
                "version": 0,
                "name": "Charte par défaut",
                "rules": DEFAULT_CHARTER,
                "author": "système",
                "note": "à personnaliser",
            }
        return dict(row)

    def publish_charter(
        self,
        rules: dict[str, Any],
        *,
        name: str,
        author: str,
        note: str | None,
        language: str | None = None,
    ) -> int:
        """Crée une version BROUILLON et la soumet au fondateur (CHARTER_CHANGE).

        La charte ne s'applique qu'après approbation (primestone.governance).
        """
        for key in ("colors", "fonts", "tone", "thumbnail"):
            if key not in rules:
                raise CreativeError(f"charte incomplète : « {key} » manquant")
        with self._engine.begin() as conn:
            version: int = conn.execute(
                text(
                    "INSERT INTO brand_charter (version, name, rules, author, note, status, "
                    "language, brand_id) VALUES ((SELECT COALESCE(max(version), 0) + 1 FROM "
                    "brand_charter), :n, CAST(:r AS jsonb), :a, :note, 'DRAFT', :lang, "
                    "(SELECT id FROM media_brand WHERE slug = 'primestone')) RETURNING version"
                ),
                {"n": name, "r": _json(rules), "a": author, "note": note, "lang": language},
            ).scalar_one()
            GovernanceService(self._engine).propose_in(
                conn,
                "CHARTER_CHANGE",
                subject_type="brand_charter",
                subject_id=str(version),
                proposal={"charter_version": version, "name": name, "note": note},
                proposed_by=author,
            )
        return version

    # --- Séries -------------------------------------------------------------------------

    def create_series(self, **fields: Any) -> UUID:
        required = ("name", "promise", "identity", "tone", "art_direction", "evolution", "author")
        if any(not str(fields.get(k) or "").strip() for k in required):
            raise CreativeError("une série exige : " + ", ".join(required))
        if not fields.get("structure"):
            raise CreativeError("une série exige une structure (étapes récurrentes)")
        with self._engine.begin() as conn:
            if conn.execute(
                text("SELECT 1 FROM series WHERE name = :n"), {"n": fields["name"]}
            ).first():
                raise CreativeError(f"série déjà définie : {fields['name']}")
            series_id: UUID = conn.execute(
                text(
                    "INSERT INTO series (name, promise, identity, segment_id, tone, structure, "
                    "target_minutes, art_direction, distribution, evolution, author, brand_id, "
                    "expertise_level, languages, evidence_requirements, pillar_id) VALUES "
                    "(:name, :promise, :identity, :segment_id, :tone, CAST(:structure AS jsonb), "
                    ":target_minutes, :art_direction, CAST(:distribution AS jsonb), "
                    ":evolution, :author, (SELECT id FROM media_brand WHERE slug = 'primestone'), "
                    ":expertise_level, CAST(:languages AS jsonb), CAST(:evidence AS jsonb), "
                    ":pillar_id) RETURNING id"
                ),
                {
                    **{
                        k: fields.get(k)
                        for k in (
                            *required,
                            "segment_id",
                            "target_minutes",
                            "expertise_level",
                            "pillar_id",
                        )
                    },
                    "structure": _json(list(fields["structure"])),
                    "distribution": _json(list(fields.get("distribution") or [])),
                    "languages": _json(list(fields.get("languages") or ["fr"])),
                    "evidence": _json(fields.get("evidence_requirements") or {}),
                },
            ).scalar_one()
            # Brouillon : le passage en test est une décision du fondateur (ADR-0028).
            ShowService(self._engine).propose_creation(conn, series_id, fields["author"])
        return series_id

    def add_episode(
        self,
        series_id: UUID,
        script_id: UUID,
        *,
        format_id: UUID | None = None,
        language: str | None = None,
    ) -> int:
        try:
            return ShowService(self._engine).add_episode(
                series_id, script_id, format_id=format_id, language=language
            )
        except ValueError as exc:
            raise CreativeError(str(exc)) from None

    def series(self) -> list[dict[str, Any]]:
        """Séries et cohérence : durée des épisodes vs cible, structure suivie, notes."""
        with self._engine.connect() as conn:
            rows = [
                dict(r)
                for r in conn.execute(
                    text(
                        "SELECT s.*, a.name AS segment FROM series s "
                        "LEFT JOIN audience_segment a ON a.id = s.segment_id ORDER BY s.name"
                    )
                ).mappings()
            ]
            episodes = (
                conn.execute(
                    text(
                        """
                SELECT e.series_id, e.number, sc.id AS script_id, sc.title,
                       (SELECT content FROM script_version v WHERE v.script_id = sc.id
                         ORDER BY number DESC LIMIT 1) AS content,
                       (SELECT ss.total FROM script_score ss JOIN script_version v
                           ON v.id = ss.version_id WHERE v.script_id = sc.id
                         ORDER BY v.number DESC, ss.created_at DESC LIMIT 1) AS total,
                       (SELECT ss.analysis -> 'words' FROM script_score ss JOIN script_version v
                           ON v.id = ss.version_id WHERE v.script_id = sc.id
                         ORDER BY v.number DESC, ss.created_at DESC LIMIT 1) AS words
                  FROM series_episode e JOIN script sc ON sc.id = e.script_id
                 ORDER BY e.number
                """
                    )
                )
                .mappings()
                .all()
            )
        for s in rows:
            eps = [e for e in episodes if e["series_id"] == s["id"]]
            issues = []
            for e in eps:
                minutes = (int(e["words"]) / 150) if e["words"] is not None else None
                if (
                    minutes is not None
                    and abs(minutes - s["target_minutes"]) > s["target_minutes"] * 0.3
                ):
                    issues.append(
                        f"épisode {e['number']} : {minutes:.0f} min "
                        f"pour une cible de {s['target_minutes']}"
                    )
                content = fold(e["content"] or "")
                missing = [b for b in s["structure"] if fold(b) not in content]
                if missing and len(missing) == len(s["structure"]):
                    issues.append(f"épisode {e['number']} : aucune étape de la structure retrouvée")
            totals = [e["total"] for e in eps if e["total"] is not None]
            s.update(
                id=str(s["id"]),
                segment_id=str(s["segment_id"]) if s["segment_id"] else None,
                episodes=[
                    {
                        "number": e["number"],
                        "title": e["title"],
                        "script_id": str(e["script_id"]),
                        "score": e["total"],
                    }
                    for e in eps
                ],
                average_score=round(mean(totals), 1) if totals else None,
                consistency=issues or ["cohérent avec la promesse, la durée et la structure"],
            )
        return rows

    # --- Packaging ----------------------------------------------------------------------

    async def package(self, script_id: UUID) -> dict[str, Any]:
        with self._engine.connect() as conn:
            row = (
                conn.execute(
                    text(
                        """
                SELECT s.title, s.level, v.number, v.content,
                       (SELECT ss.analysis -> 'fact_check' -> 'checks' FROM script_score ss
                         WHERE ss.version_id = v.id ORDER BY ss.created_at DESC LIMIT 1) AS checks
                  FROM script s JOIN script_version v ON v.script_id = s.id
                 WHERE s.id = :s ORDER BY v.number DESC LIMIT 1
                """
                    ),
                    {"s": script_id},
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise LookupError("script introuvable ou sans version")
        if row["checks"] is None:
            raise CreativeError(
                "évaluer d'abord le script : le packaging repose sur ses faits vérifiés"
            )
        facts = [c["sentence"] for c in row["checks"] if c["status"] == "VERIFIED"]
        charter = self.charter()
        extra: Sequence[str] = []
        if self._title_writer is not None:
            try:
                extra = (await self._title_writer(row["title"], row["content"]))[:10]
            except Exception:  # le modèle local est facultatif
                extra = []
        result = build(
            subject=row["title"],
            script=row["content"],
            verified_facts=facts,
            charter=charter["rules"],
            level=row["level"],
            extra_titles=extra,
        )
        result["charter_version"] = charter["version"]
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO packaging_set (script_id, script_version, method, "
                    "charter_version, "
                    "content) VALUES (:s, :v, :m, :c, CAST(:content AS jsonb))"
                ),
                {
                    "s": script_id,
                    "v": row["number"],
                    "m": METHOD,
                    "c": charter["version"],
                    "content": _json(result),
                },
            )
        return result

    def packagings(self, script_id: UUID) -> list[dict[str, Any]]:
        with self._engine.connect() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    text(
                        "SELECT script_version, method, charter_version, content, created_at "
                        "FROM packaging_set WHERE script_id = :s ORDER BY created_at DESC"
                    ),
                    {"s": script_id},
                ).mappings()
            ]
