"""Émissions (`series` étendue) : chaque transition, chaque changement de règles et chaque
validation finale d'épisode est une décision du fondateur (primestone.governance).

Une émission suspendue, retirée ou encore en brouillon n'accepte aucun nouvel épisode ; un
épisode respecte un format, et tout écart est signalé, jamais masqué.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, Engine, text

from primestone.forensic import fold
from primestone.governance.service import GovernanceError, GovernanceService, register_handler

TRANSITIONS = {
    ("DRAFT", "TESTING"),
    ("DRAFT", "RETIRED"),
    ("TESTING", "ACTIVE"),
    ("TESTING", "RETIRED"),
    ("ACTIVE", "SUSPENDED"),
    ("SUSPENDED", "ACTIVE"),
    ("ACTIVE", "RETIRED"),
    ("SUSPENDED", "RETIRED"),
}
ACCEPTING = ("TESTING", "ACTIVE")
GUIDELINE_FIELDS = {
    "promise": "text",
    "identity": "text",
    "tone": "text",
    "art_direction": "text",
    "evolution": "text",
    "target_minutes": "int",
    "expertise_level": "text",
    "pillar_id": "uuid",
    "structure": "json",
    "distribution": "json",
    "languages": "json",
    "evidence_requirements": "json",
}
WORDS_PER_MINUTE = 150
METHOD_FIT = "show-fit@1"


class ShowError(ValueError):
    pass


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _set_fields(conn: Connection, series_id: Any, fields: dict[str, Any]) -> None:
    for key, value in fields.items():
        kind = GUIDELINE_FIELDS[key]
        expr = "CAST(:v AS jsonb)" if kind == "json" else ":v"
        conn.execute(
            # Nom de colonne pris dans GUIDELINE_FIELDS (liste fixe), jamais dans l'entrée.
            text(f"UPDATE series SET {key} = {expr}, updated_at = now() WHERE id = :id"),  # noqa: S608
            {"v": _json(value) if kind == "json" else value, "id": series_id},
        )


# --- Gestionnaires de gouvernance ------------------------------------------------------------


def _lifecycle(conn: Connection, decision: dict[str, Any], forward: bool) -> dict[str, Any] | None:
    start, end = decision["proposal"]["from"], decision["proposal"]["to"]
    expected, target = (start, end) if forward else (end, start)
    current = conn.execute(
        text("SELECT status FROM series WHERE id = :id FOR UPDATE"), {"id": decision["subject_id"]}
    ).scalar_one()
    if current != expected:
        raise GovernanceError(f"l'émission est {current}, la décision suppose {expected}")
    conn.execute(
        text("UPDATE series SET status = :s, updated_at = now() WHERE id = :id"),
        {"s": target, "id": decision["subject_id"]},
    )
    return {"status": start} if forward else None


def _guidelines(conn: Connection, decision: dict[str, Any], forward: bool) -> dict[str, Any] | None:
    proposal = decision["proposal"]
    series_id = decision["subject_id"]
    if forward:
        keys = list(proposal["guidelines"])
        row = (
            conn.execute(text("SELECT * FROM series WHERE id = :id FOR UPDATE"), {"id": series_id})
            .mappings()
            .one()
        )
        previous = {k: row[k] for k in keys}
        _set_fields(conn, series_id, proposal["guidelines"])
        conn.execute(
            text("UPDATE series SET guideline_version = :v WHERE id = :id"),
            {"v": proposal["version"], "id": series_id},
        )
        return {"fields": previous, "guideline_version": row["guideline_version"]}
    before = proposal.get("previous") or {}
    _set_fields(conn, series_id, before.get("fields", {}))
    conn.execute(
        text("UPDATE series SET guideline_version = :v WHERE id = :id"),
        {"v": before.get("guideline_version", 1), "id": series_id},
    )
    return None


def _final_validation(
    conn: Connection, decision: dict[str, Any], forward: bool
) -> dict[str, Any] | None:
    episode_id = decision["subject_id"]
    if forward:
        row = (
            conn.execute(
                text(
                    "SELECT e.status, s.status AS script_status FROM series_episode e "
                    "JOIN script s ON s.id = e.script_id WHERE e.id = :id FOR UPDATE OF e"
                ),
                {"id": episode_id},
            )
            .mappings()
            .one()
        )
        if row["script_status"] != "VALIDATED":
            raise GovernanceError(
                "le script de l'épisode n'est pas validé (vérification factuelle)"
            )
        if row["status"] not in ("PROPOSED", "IN_PRODUCTION"):
            raise GovernanceError(f"épisode déjà {row['status']}")
        conn.execute(
            text("UPDATE series_episode SET status = 'APPROVED' WHERE id = :id"), {"id": episode_id}
        )
        return {"status": row["status"]}
    status = conn.execute(
        text("SELECT status FROM series_episode WHERE id = :id FOR UPDATE"), {"id": episode_id}
    ).scalar_one()
    if status != "APPROVED":
        raise GovernanceError("épisode déjà publié : l'annulation ne peut pas le dépublier")
    conn.execute(
        text("UPDATE series_episode SET status = :s WHERE id = :id"),
        {
            "s": (decision["proposal"].get("previous") or {}).get("status", "PROPOSED"),
            "id": episode_id,
        },
    )
    return None


register_handler("SHOW_LIFECYCLE", _lifecycle)
register_handler("SHOW_GUIDELINES", _guidelines)
register_handler("SCRIPT_FINAL_VALIDATION", _final_validation)


class ShowService:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._governance = GovernanceService(engine)

    # --- Cycle de vie -----------------------------------------------------------------------

    def propose_creation(self, conn: Connection, series_id: UUID, author: str) -> dict[str, Any]:
        """Une émission naît en brouillon ; son passage en test est soumis au fondateur."""
        return self._governance.propose_in(
            conn,
            "SHOW_LIFECYCLE",
            subject_type="series",
            subject_id=str(series_id),
            proposal={"from": "DRAFT", "to": "TESTING"},
            proposed_by=author,
        )

    def transition(
        self, series_id: UUID, to: str, *, proposed_by: str, reason: str | None = None
    ) -> dict[str, Any]:
        with self._engine.begin() as conn:
            current = conn.execute(
                text("SELECT status FROM series WHERE id = :id FOR UPDATE"), {"id": series_id}
            ).scalar_one_or_none()
            if current is None:
                raise LookupError("émission introuvable")
            if (current, to) not in TRANSITIONS:
                raise ShowError(f"transition interdite : {current} → {to}")
            if conn.execute(
                text(
                    "SELECT 1 FROM editorial_decision WHERE action = 'SHOW_LIFECYCLE' "
                    "AND subject_id = :id AND status = 'PROPOSED'"
                ),
                {"id": str(series_id)},
            ).first():
                raise ShowError("une transition est déjà en attente de décision")
            return self._governance.propose_in(
                conn,
                "SHOW_LIFECYCLE",
                subject_type="series",
                subject_id=str(series_id),
                proposal={"from": current, "to": to, "reason": reason},
                proposed_by=proposed_by,
            )

    # --- Règles versionnées -----------------------------------------------------------------

    def propose_guidelines(
        self, series_id: UUID, changes: dict[str, Any], *, author: str
    ) -> dict[str, Any]:
        unknown = set(changes) - set(GUIDELINE_FIELDS)
        if not changes or unknown:
            raise ShowError(f"règles inconnues ou vides : {sorted(unknown)}")
        languages = changes.get("languages")
        if languages is not None and (
            not languages or any(lang not in ("fr", "en") for lang in languages)
        ):
            raise ShowError("langues possibles : fr, en")
        with self._engine.begin() as conn:
            current = conn.execute(
                text("SELECT guideline_version FROM series WHERE id = :id FOR UPDATE"),
                {"id": series_id},
            ).scalar_one_or_none()
            if current is None:
                raise LookupError("émission introuvable")
            last = conn.execute(
                text("SELECT max(version) FROM show_guideline_version WHERE series_id = :id"),
                {"id": series_id},
            ).scalar_one()
            version = max(current, last or 0) + 1
            decision = self._governance.propose_in(
                conn,
                "SHOW_GUIDELINES",
                subject_type="series",
                subject_id=str(series_id),
                proposal={"version": version, "guidelines": changes},
                proposed_by=author,
            )
            conn.execute(
                text(
                    "INSERT INTO show_guideline_version (series_id, version, guidelines, "
                    "decision_id, author) VALUES (:s, :v, CAST(:g AS jsonb), :d, :a)"
                ),
                {
                    "s": series_id,
                    "v": version,
                    "g": _json(changes),
                    "d": decision["decision_id"],
                    "a": author,
                },
            )
        return decision | {"version": version}

    def guidelines(self, series_id: UUID) -> list[dict[str, Any]]:
        with self._engine.connect() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    text(
                        "SELECT g.version, g.guidelines, g.author, g.created_at, "
                        "d.status AS decision_status, d.id AS decision_id "
                        "FROM show_guideline_version g JOIN editorial_decision d "
                        "ON d.id = g.decision_id WHERE g.series_id = :s ORDER BY g.version"
                    ),
                    {"s": series_id},
                ).mappings()
            ]

    # --- Formats ----------------------------------------------------------------------------

    def add_format(
        self,
        series_id: UUID,
        *,
        name: str,
        platform: str,
        language: str,
        min_minutes: float,
        max_minutes: float,
        structure: list[str],
        rules: dict[str, Any] | None = None,
    ) -> UUID:
        if not structure:
            raise ShowError("un format exige une structure")
        if not 0 < min_minutes <= max_minutes:
            raise ShowError("durées incohérentes")
        with self._engine.begin() as conn:
            languages = conn.execute(
                text("SELECT languages FROM series WHERE id = :id"), {"id": series_id}
            ).scalar_one_or_none()
            if languages is None:
                raise LookupError("émission introuvable")
            if language not in languages:
                raise ShowError(f"langue {language} absente de la stratégie de l'émission")
            if conn.execute(
                text(
                    "SELECT 1 FROM show_format WHERE series_id = :s AND name = :n AND language = :l"
                ),
                {"s": series_id, "n": name, "l": language},
            ).first():
                raise ShowError(f"format déjà défini : {name} ({language})")
            format_id: UUID = conn.execute(
                text(
                    "INSERT INTO show_format (series_id, name, platform, language, min_minutes, "
                    "max_minutes, structure, rules) VALUES (:s, :n, :p, :l, :mi, :ma, "
                    "CAST(:st AS jsonb), CAST(:r AS jsonb)) RETURNING id"
                ),
                {
                    "s": series_id,
                    "n": name,
                    "p": platform,
                    "l": language,
                    "mi": min_minutes,
                    "ma": max_minutes,
                    "st": _json(structure),
                    "r": _json(rules or {}),
                },
            ).scalar_one()
        return format_id

    def retire_format(self, format_id: UUID) -> None:
        with self._engine.begin() as conn:
            if not conn.execute(
                text(
                    "UPDATE show_format SET status = 'RETIRED', version = version + 1 "
                    "WHERE id = :id AND status = 'ACTIVE' RETURNING id"
                ),
                {"id": format_id},
            ).first():
                raise LookupError("format actif introuvable")

    # --- Épisodes ---------------------------------------------------------------------------

    def add_episode(
        self,
        series_id: UUID,
        script_id: UUID,
        *,
        format_id: UUID | None = None,
        language: str | None = None,
    ) -> int:
        with self._engine.begin() as conn:
            show = (
                conn.execute(
                    text(
                        "SELECT status, languages, guideline_version FROM series "
                        "WHERE id = :s FOR UPDATE"
                    ),
                    {"s": series_id},
                )
                .mappings()
                .one_or_none()
            )
            if show is None:
                raise LookupError("série introuvable")
            if show["status"] not in ACCEPTING:
                raise ShowError(f"émission {show['status']} : aucun nouvel épisode accepté")
            script_language = conn.execute(
                text("SELECT language FROM script WHERE id = :sc"), {"sc": script_id}
            ).scalar_one_or_none()
            if script_language is None:
                raise LookupError("script introuvable")
            if conn.execute(
                text("SELECT 1 FROM series_episode WHERE script_id = :sc"), {"sc": script_id}
            ).first():
                raise ShowError("ce script appartient déjà à une série")
            if format_id is not None:
                fmt = (
                    conn.execute(
                        text(
                            "SELECT language FROM show_format WHERE id = :f AND series_id = :s "
                            "AND status = 'ACTIVE'"
                        ),
                        {"f": format_id, "s": series_id},
                    )
                    .mappings()
                    .one_or_none()
                )
                if fmt is None:
                    raise ShowError("format inconnu, retiré ou d'une autre émission")
                language = language or fmt["language"]
                if language != fmt["language"]:
                    raise ShowError("la langue de l'épisode diffère de celle du format")
            language = language or script_language
            if language not in show["languages"]:
                raise ShowError(f"langue {language} absente de la stratégie de l'émission")
            number: int = conn.execute(
                text(
                    "INSERT INTO series_episode (series_id, script_id, number, format_id, "
                    "language, guideline_version) VALUES (:s, :sc, (SELECT COALESCE(max(number), "
                    "0) + 1 FROM series_episode WHERE series_id = :s), :f, :l, :g) "
                    "RETURNING number"
                ),
                {
                    "s": series_id,
                    "sc": script_id,
                    "f": format_id,
                    "l": language,
                    "g": show["guideline_version"],
                },
            ).scalar_one()
            conn.execute(
                text("UPDATE script SET show_id = :s, format_id = :f WHERE id = :sc"),
                {"s": series_id, "f": format_id, "sc": script_id},
            )
        return number

    def _episode(self, conn: Connection, series_id: UUID, number: int) -> dict[str, Any]:
        row = (
            conn.execute(
                text(
                    "SELECT id, status FROM series_episode WHERE series_id = :s AND number = :n "
                    "FOR UPDATE"
                ),
                {"s": series_id, "n": number},
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise LookupError("épisode introuvable")
        return dict(row)

    def start_production(self, series_id: UUID, number: int) -> None:
        with self._engine.begin() as conn:
            episode = self._episode(conn, series_id, number)
            if episode["status"] != "PROPOSED":
                raise ShowError(f"épisode déjà {episode['status']}")
            conn.execute(
                text("UPDATE series_episode SET status = 'IN_PRODUCTION' WHERE id = :id"),
                {"id": episode["id"]},
            )

    def propose_final_validation(
        self, series_id: UUID, number: int, *, proposed_by: str
    ) -> dict[str, Any]:
        with self._engine.begin() as conn:
            episode = self._episode(conn, series_id, number)
            return self._governance.propose_in(
                conn,
                "SCRIPT_FINAL_VALIDATION",
                subject_type="series_episode",
                subject_id=str(episode["id"]),
                proposal={"series_id": str(series_id), "number": number},
                proposed_by=proposed_by,
            )

    def declare_published(self, series_id: UUID, number: int, content_id: UUID) -> None:
        """Déclare une publication faite par le propriétaire (aucune publication automatique)."""
        with self._engine.begin() as conn:
            episode = self._episode(conn, series_id, number)
            if episode["status"] != "APPROVED":
                raise ShowError(
                    "seul un épisode approuvé par le fondateur peut être déclaré publié"
                )
            if not conn.execute(
                text("UPDATE content_item SET show_id = :s WHERE id = :c RETURNING id"),
                {"s": series_id, "c": content_id},
            ).first():
                raise LookupError("contenu introuvable (importer d'abord les statistiques)")
            conn.execute(
                text(
                    "UPDATE series_episode SET status = 'PUBLISHED', content_id = :c WHERE id = :id"
                ),
                {"c": content_id, "id": episode["id"]},
            )

    # --- Lecture ----------------------------------------------------------------------------

    def show(self, series_id: UUID) -> dict[str, Any]:
        with self._engine.connect() as conn:
            row = (
                conn.execute(
                    text(
                        "SELECT s.*, p.name AS pillar FROM series s LEFT JOIN editorial_pillar p "
                        "ON p.id = s.pillar_id WHERE s.id = :id"
                    ),
                    {"id": series_id},
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise LookupError("émission introuvable")
            formats = [
                dict(r)
                for r in conn.execute(
                    text(
                        "SELECT id, name, platform, language, min_minutes, max_minutes, "
                        "structure, rules, version, status FROM show_format "
                        "WHERE series_id = :s ORDER BY language, name"
                    ),
                    {"s": series_id},
                ).mappings()
            ]
            episodes = [
                dict(r)
                for r in conn.execute(
                    text(
                        """
                SELECT e.id, e.number, e.status, e.language, e.format_id, e.content_id,
                       e.guideline_version, sc.id AS script_id, sc.title,
                       sc.status AS script_status,
                       (SELECT content FROM script_version v WHERE v.script_id = sc.id
                         ORDER BY number DESC LIMIT 1) AS content
                  FROM series_episode e JOIN script sc ON sc.id = e.script_id
                 WHERE e.series_id = :s ORDER BY e.number
                """
                    ),
                    {"s": series_id},
                ).mappings()
            ]
            pending = [
                dict(r)
                for r in conn.execute(
                    text(
                        "SELECT id, action, proposal, proposed_by, created_at "
                        "FROM editorial_decision WHERE status = 'PROPOSED' AND "
                        "((subject_type = 'series' AND subject_id = :s) OR "
                        "(subject_type = 'series_episode' AND subject_id = ANY(:e)))"
                    ),
                    {"s": str(series_id), "e": [str(e["id"]) for e in episodes]},
                ).mappings()
            ]
        by_id = {f["id"]: f for f in formats}
        for e in episodes:
            e["conformance"] = conformance(e.pop("content") or "", by_id.get(e["format_id"]))
        return dict(row) | {"formats": formats, "episodes": episodes, "pending": pending}

    def performance(self, series_id: UUID) -> dict[str, Any]:
        """Agrège les statistiques AUTORISÉES des contenus de l'émission (dernière mesure)."""
        with self._engine.connect() as conn:
            rows = (
                conn.execute(
                    text(
                        """
                WITH contents AS (
                  SELECT c.id, c.language, c.format FROM content_item c
                   WHERE c.show_id = :s
                      OR c.id IN (SELECT content_id FROM series_episode WHERE series_id = :s)
                      OR c.script_id IN (SELECT script_id FROM series_episode
                                          WHERE series_id = :s)
                ), latest AS (
                  SELECT DISTINCT ON (m.content_id, m.metric) m.content_id, m.metric, m.value
                    FROM performance_metric m JOIN contents c ON c.id = m.content_id
                   WHERE m.dimension IS NULL
                   ORDER BY m.content_id, m.metric, m.observed_at DESC
                )
                SELECT c.id, c.language, c.format, l.metric, l.value
                  FROM contents c LEFT JOIN latest l ON l.content_id = c.id
                """
                    ),
                    {"s": series_id},
                )
                .mappings()
                .all()
            )
        contents = {r["id"] for r in rows}
        if not contents:
            return {"series_id": str(series_id), "contents": 0, "status": "NON FOURNI"}

        by_language: dict[str, list[Any]] = {}
        by_format: dict[str, list[Any]] = {}
        for r in rows:
            by_language.setdefault(r["language"] or "inconnue", []).append(r)
            by_format.setdefault(r["format"] or "inconnu", []).append(r)
        return {
            "series_id": str(series_id),
            "data_class": "PRIVATE_AUTHORIZED",
            "total": aggregate(list(rows)),
            "by_language": {k: aggregate(v) for k, v in by_language.items()},
            "by_format": {k: aggregate(v) for k, v in by_format.items()},
            "rule": "Agrégats observés ; aucune causalité sans expérience contrôlée.",
        }

    def fit(self, subject: str, *, language: str | None = None) -> dict[str, Any]:
        """Adéquation d'un sujet (opportunité) aux émissions ouvertes et aux piliers actifs."""
        terms = {w for w in fold(subject).split() if len(w) > 3}
        with self._engine.connect() as conn:
            shows = (
                conn.execute(
                    text(
                        "SELECT s.id, s.name, s.promise, s.identity, s.status, s.languages, "
                        "p.name AS pillar, p.description AS pillar_description "
                        "FROM series s LEFT JOIN editorial_pillar p ON p.id = s.pillar_id "
                        "WHERE s.status IN ('TESTING', 'ACTIVE')"
                    )
                )
                .mappings()
                .all()
            )
            pillars = (
                conn.execute(
                    text(
                        "SELECT id, name, description FROM editorial_pillar WHERE status = 'ACTIVE'"
                    )
                )
                .mappings()
                .all()
            )

        def score(*texts: str | None) -> list[str]:
            words = set(fold(" ".join(t or "" for t in texts)).split())
            return sorted(terms & words)

        ranked = []
        for s in shows:
            if language and language not in s["languages"]:
                continue
            matched = score(
                s["name"], s["promise"], s["identity"], s["pillar"], s["pillar_description"]
            )
            if matched:
                ranked.append(
                    {
                        "series_id": str(s["id"]),
                        "name": s["name"],
                        "status": s["status"],
                        "matched": matched,
                    }
                )
        ranked.sort(key=lambda r: -len(r["matched"]))
        pillar_fit = [
            {"pillar_id": str(p["id"]), "name": p["name"], "matched": m}
            for p in pillars
            if (m := score(p["name"], p["description"]))
        ]
        return {
            "method": METHOD_FIT,
            "subject": subject,
            "shows": ranked,
            "pillars": pillar_fit,
            "rule": "Adéquation lexicale indicative ; le choix de l'émission revient au fondateur.",
        }


def aggregate(subset: list[Any]) -> dict[str, Any]:
    """Somme des volumes, moyenne des taux, sur la dernière mesure de chaque contenu."""
    values: dict[str, list[float]] = {}
    for r in subset:
        if r["metric"] is not None:
            values.setdefault(r["metric"], []).append(float(r["value"]))
    out: dict[str, Any] = {"contents": len({r["id"] for r in subset})}
    for metric in ("views", "impressions", "watch_time_min", "subscribers_gained"):
        if metric in values:
            out[metric] = round(sum(values[metric]), 2)
    for metric in ("ctr", "avg_view_percentage", "avg_view_duration_s"):
        if metric in values:
            out[f"{metric}_mean"] = round(sum(values[metric]) / len(values[metric]), 2)
    return out


def conformance(content: str, fmt: dict[str, Any] | None) -> list[str]:
    """Écarts d'un épisode à son format : durée estimée et étapes de structure absentes."""
    if fmt is None:
        return ["aucun format : conformité non vérifiable"]
    issues = []
    minutes = len(content.split()) / WORDS_PER_MINUTE
    if not float(fmt["min_minutes"]) <= minutes <= float(fmt["max_minutes"]):
        issues.append(
            f"durée estimée {minutes:.1f} min hors format "
            f"({fmt['min_minutes']} à {fmt['max_minutes']} min)"
        )
    folded = fold(content)
    missing = [step for step in fmt["structure"] if fold(step) not in folded]
    if missing:
        issues.append("étapes absentes : " + ", ".join(missing))
    return issues or ["conforme au format"]
