"""Content Performance Lab (méthode `perf-lab@1`) et validation de l'extension.

RESEARCH → STRATEGY → SCRIPT → PRODUCTION → PUBLISH → MEASURE → DIAGNOSE → LEARN → OPTIMIZE.
Chaque conclusion porte son niveau de preuve : OBSERVED (mesuré), HYPOTHESIS (corrélation ou
repère du script), DEMONSTRATED (expérience concluante, dans son contexte).
"""

from __future__ import annotations

from collections import defaultdict
from statistics import median
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, Engine, text

from primestone.forensic import fold

METHOD = "perf-lab@1"
LOOP = (
    "RESEARCH",
    "STRATEGY",
    "SCRIPT",
    "PRODUCTION",
    "PUBLISH",
    "MEASURE",
    "DIAGNOSE",
    "LEARN",
    "OPTIMIZE",
)
EARLY = 0.1  # début de vidéo : 10 % de la durée

_CURVE = """
    SELECT elapsed_ratio, audience_watch_ratio FROM retention_point
     WHERE content_id = :c
       AND observed_at = (SELECT max(observed_at) FROM retention_point WHERE content_id = :c)
     ORDER BY elapsed_ratio
"""
_LATEST_SCRIPT = """
    SELECT c.id, (SELECT content FROM script_version v WHERE v.script_id = c.script_id
                   ORDER BY number DESC LIMIT 1) AS content
      FROM content_item c WHERE c.script_id IS NOT NULL
"""
_LOOP_QUERIES = {
    "STRATEGY": """
        SELECT (SELECT count(*) FROM series_episode WHERE script_id = :s)
             + (SELECT count(*) FROM script WHERE id = :s AND level IS NOT NULL)
    """,
    "SCRIPT": "SELECT count(*) FROM script_version WHERE script_id = :s",
    "PRODUCTION": """
        SELECT (SELECT count(*) FROM packaging_set WHERE script_id = :s)
             + (SELECT count(*) FROM script WHERE id = :s AND status = 'VALIDATED')
    """,
    "PUBLISH": "SELECT count(*) FROM content_item WHERE script_id = :s",
    "MEASURE": """
        SELECT count(*) FROM performance_metric m
          JOIN content_item c ON c.id = m.content_id WHERE c.script_id = :s
    """,
    "DIAGNOSE": """
        SELECT count(*) FROM retention_point p
          JOIN content_item c ON c.id = p.content_id WHERE c.script_id = :s
    """,
    "LEARN": """
        SELECT count(*) FROM experiment e
          JOIN content_item c ON e.content_ids ? c.id::text WHERE c.script_id = :s
    """,
    "OPTIMIZE": "SELECT (count(*) > 1)::int FROM script_version WHERE script_id = :s",
}
# Les 13 critères de validation de l'extension : (libellé, requête de preuve, ce qu'il manque).
_CRITERIA = (
    (
        "Compréhension structurée des audiences",
        "SELECT count(*) FROM audience_evidence WHERE retracted_at IS NULL",
        "un segment avec des preuves",
    ),
    (
        "Segmentation fondée sur des données",
        "SELECT count(*) FROM audience_segment WHERE status = 'CONFIRMED'",
        "un segment CONFIRMED",
    ),
    (
        "Détection argumentée d'opportunités",
        "SELECT count(*) FROM market_topic",
        "des sujets suivis avec données FR (voir /market)",
    ),
    (
        "Scripts à plusieurs niveaux",
        "SELECT count(*) FROM script WHERE level_of IS NOT NULL",
        "une variante de niveau",
    ),
    (
        "Génération et évaluation de packaging",
        "SELECT count(*) FROM packaging_set",
        "un packaging",
    ),
    (
        "Analyse de vidéos publiées",
        "SELECT count(*) FROM content_item WHERE script_id IS NOT NULL",
        "une vidéo reliée à son script",
    ),
    (
        "Exploitation des statistiques autorisées",
        "SELECT count(*) FROM performance_metric",
        "un import Studio ou une synchronisation",
    ),
    (
        "Apprentissage à partir des résultats",
        "SELECT count(*) FROM experiment WHERE status IN ('CONCLUDED', 'INCONCLUSIVE')",
        "une expérience close",
    ),
    (
        "Création de franchises éditoriales",
        """
        SELECT count(*) FROM series s
         WHERE (SELECT count(*) FROM series_episode e WHERE e.series_id = s.id) >= 2
        """,
        "une série d'au moins 2 épisodes",
    ),
    (
        "Déclinaison multi-plateforme",
        "SELECT count(*) FROM mission WHERE type = 'SOCIAL_PACKAGE' AND status = 'APPROVED'",
        "un paquet social approuvé",
    ),
    (
        "Adaptation française et anglaise",
        "SELECT count(*) FROM script WHERE adapted_from IS NOT NULL",
        "une adaptation reliée",
    ),
    (
        "Cohérence de marque",
        "SELECT count(*) FROM brand_charter",
        "une charte personnalisée publiée",
    ),
    (
        "Mesure fiable de la qualité et de la croissance",
        "SELECT count(*) FROM content_item WHERE objective IS NOT NULL",
        "des vidéos classées par objectif",
    ),
)


def hook_type(first_sentence: str) -> str:
    folded = fold(first_sentence)
    if "?" in first_sentence:
        return "QUESTION"
    if any(m in f" {folded} " for m in (" pourtant ", " paradoxe ", " mais ", " yet ", " but ")):
        return "PARADOXE"
    if "«" in first_sentence or first_sentence.strip().startswith('"'):
        return "CITATION"
    return "AFFIRMATION"


def _first_spoken_line(script: str) -> str:
    """Première ligne de texte dit (après le premier titre ou horodatage)."""
    lines = [line.strip() for line in script.splitlines() if line.strip()]
    return lines[1] if len(lines) > 1 else (lines[0] if lines else "")


class PerformanceLab:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    @staticmethod
    def _curve(conn: Connection, content_id: UUID) -> list[dict[str, float]]:
        return [
            {"elapsed_ratio": float(r[0]), "audience_watch_ratio": float(r[1])}
            for r in conn.execute(text(_CURVE), {"c": content_id}).all()
        ]

    def autopsy(self, content_id: UUID) -> dict[str, Any]:
        """Diagnostic d'une vidéo publiée : ce qui est observé, ce qui reste hypothèse."""
        with self._engine.connect() as conn:
            content = (
                conn.execute(
                    text(
                        """
                        SELECT c.id, c.title, c.objective, c.format, c.script_id,
                               s.title AS script_title
                          FROM content_item c LEFT JOIN script s ON s.id = c.script_id
                         WHERE c.id = :c
                        """
                    ),
                    {"c": content_id},
                )
                .mappings()
                .one_or_none()
            )
            if content is None:
                raise LookupError("contenu introuvable")
            metrics = {
                str(m): float(v)
                for m, v in conn.execute(
                    text(
                        """
                        SELECT DISTINCT ON (metric) metric, value FROM performance_metric
                         WHERE content_id = :c AND dimension IS NULL
                         ORDER BY metric, observed_at DESC
                        """
                    ),
                    {"c": content_id},
                ).all()
            }
            curve = self._curve(conn, content_id)
            script = None
            if content["script_id"]:
                script = (
                    conn.execute(
                        text(
                            """
                            SELECT v.content,
                                   (SELECT criteria FROM script_score ss
                                     WHERE ss.version_id = v.id
                                     ORDER BY created_at DESC LIMIT 1) AS criteria
                              FROM script_version v WHERE v.script_id = :s
                             ORDER BY v.number DESC LIMIT 1
                            """
                        ),
                        {"s": content["script_id"]},
                    )
                    .mappings()
                    .one_or_none()
                )
            comments = {
                str(k): int(n)
                for k, n in conn.execute(
                    text(
                        "SELECT kind, count(*) FROM community_comment "
                        "WHERE content_id = :c GROUP BY kind"
                    ),
                    {"c": content_id},
                ).all()
            }
            experiments = [
                dict(r)
                for r in conn.execute(
                    text(
                        "SELECT title, variable, status, result ->> 'winner' AS winner "
                        "FROM experiment WHERE content_ids ? :c"
                    ),
                    {"c": str(content_id)},
                ).mappings()
            ]
        findings: list[dict[str, str]] = []
        if script:
            retention = _analyze_retention(script["content"], curve)
            for drop in retention["drop_offs"]:
                findings.append(
                    {
                        "evidence": "OBSERVED",
                        "finding": f"décrochage de {abs(drop['drop']):.0%} à "
                        f"{drop['at_ratio']:.0%} (section « {drop['section']} »)",
                    }
                )
            for section in retention["sections"]:
                for flag in section["flags"]:
                    findings.append(
                        {"evidence": "HYPOTHESIS", "finding": f"{section['title']} : {flag}"}
                    )
            criteria = script["criteria"] or {}
            weak = [k for k, c in criteria.items() if c["score"] < c["max"] * 0.5]
            if weak:
                findings.append(
                    {"evidence": "HYPOTHESIS", "finding": "critères faibles : " + ", ".join(weak)}
                )
        elif curve:
            findings.append(
                {
                    "evidence": "OBSERVED",
                    "finding": "courbe disponible, vidéo non reliée à un script",
                }
            )
        for e in experiments:
            if e["status"] == "CONCLUDED":
                findings.append(
                    {
                        "evidence": "DEMONSTRATED",
                        "finding": f"{e['title']} : variante {e['winner']}",
                    }
                )
        if comments.get("QUESTION"):
            findings.append(
                {
                    "evidence": "OBSERVED",
                    "finding": f"{comments['QUESTION']} question(s) du public : suite possible",
                }
            )
        missing = [
            label
            for label, present in (
                ("objectif", content["objective"]),
                ("script relié", content["script_id"]),
                ("courbe de rétention", curve),
            )
            if not present
        ]
        return {
            "method": METHOD,
            "content": {
                "title": content["title"],
                "objective": content["objective"],
                "format": content["format"],
                "script": content["script_title"],
            },
            "metrics": metrics,
            "has_curve": bool(curve),
            "findings": findings,
            "missing": missing,
        }

    def hooks(self) -> dict[str, Any]:
        """Type d'accroche (première phrase dite) face à la rétention en début de vidéo."""
        rows: dict[str, list[float]] = defaultdict(list)
        with self._engine.connect() as conn:
            for content_id, script in conn.execute(text(_LATEST_SCRIPT)).all():
                early = [
                    p["audience_watch_ratio"]
                    for p in self._curve(conn, content_id)
                    if p["elapsed_ratio"] <= EARLY
                ]
                if early and script:
                    rows[hook_type(_first_spoken_line(script))].append(min(early))
        table = [
            {
                "hook": hook,
                "videos": len(values),
                "median_early_retention": round(median(values), 3),
                "evidence": "OBSERVED" if len(values) >= 3 else "INSUFFISANT",
            }
            for hook, values in rows.items()
        ]
        return {
            "method": METHOD,
            "early_window": EARLY,
            "hooks": sorted(table, key=lambda r: -r["videos"]),
            "note": "Comparaison observée, pas une cause : la confirmer par une expérience HOOK.",
        }

    def drop_offs(self) -> dict[str, Any]:
        """Décrochages observés, agrégés par section de script (vidéos reliées)."""
        counter: dict[str, int] = defaultdict(int)
        with self._engine.connect() as conn:
            for content_id, script in conn.execute(text(_LATEST_SCRIPT)).all():
                curve = self._curve(conn, content_id)
                for drop in _analyze_retention(script or "", curve)["drop_offs"]:
                    counter[drop["section"] or "?"] += 1
        return {
            "method": METHOD,
            "evidence": "OBSERVED",
            "sections": sorted(
                ({"section": k, "drops": v} for k, v in counter.items()), key=lambda r: -r["drops"]
            ),
        }

    def returning(self) -> dict[str, Any]:
        """Part de spectateurs connus par objectif (si la plateforme la fournit)."""
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT c.objective, r.value, u.value
                      FROM content_item c
                      JOIN LATERAL (SELECT value FROM performance_metric
                                     WHERE content_id = c.id AND metric = 'returning_viewers'
                                       AND dimension IS NULL
                                     ORDER BY observed_at DESC LIMIT 1) r ON true
                      JOIN LATERAL (SELECT value FROM performance_metric
                                     WHERE content_id = c.id AND metric = 'unique_viewers'
                                       AND dimension IS NULL
                                     ORDER BY observed_at DESC LIMIT 1) u ON true
                    """
                )
            ).all()
        by: dict[str, list[float]] = defaultdict(list)
        for objective, returning, uniques in rows:
            if uniques:
                by[objective or "NON CLASSÉ"].append(float(returning) / float(uniques))
        return {
            "method": METHOD,
            "evidence": "OBSERVED" if by else "NON FOURNI",
            "by_objective": {k: round(median(v), 3) for k, v in by.items()},
            "note": "Spectateurs connus / uniques ; exige ces deux métriques (export ou API).",
        }

    def loop(self, script_id: UUID) -> dict[str, Any]:
        """Où en est un sujet dans la boucle RESEARCH → … → OPTIMIZE."""
        with self._engine.connect() as conn:
            row = (
                conn.execute(
                    text("SELECT title, document_ids FROM script WHERE id = :s"), {"s": script_id}
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise LookupError("script introuvable")
            done = {"RESEARCH": bool(row["document_ids"])}
            for step, sql in _LOOP_QUERIES.items():
                done[step] = conn.execute(text(sql), {"s": script_id}).scalar_one() > 0
        return {
            "script": row["title"],
            "loop": [{"step": step, "done": done[step]} for step in LOOP],
            "next": next((step for step in LOOP if not done[step]), None),
        }

    def validation(self) -> dict[str, Any]:
        """Les 13 critères de l'extension : DEMONSTRATED seulement sur données en base."""
        rows = []
        with self._engine.connect() as conn:
            for label, sql, need in _CRITERIA:
                count = conn.execute(text(sql)).scalar_one()
                rows.append(
                    {
                        "criterion": label,
                        "status": "DEMONSTRATED" if count else "NOT YET",
                        "evidence_count": count,
                        "needed": None if count else need,
                    }
                )
        demonstrated = sum(1 for r in rows if r["status"] == "DEMONSTRATED")
        return {
            "method": METHOD,
            "criteria": rows,
            "demonstrated": demonstrated,
            "total": len(rows),
            "complete": demonstrated == len(rows),
            "rule": "Complète seulement quand les 13 critères sont démontrés sur données réelles.",
        }


def _analyze_retention(script: str, curve: Any) -> dict[str, Any]:
    # Import différé : storytelling → editorial → performance formerait un cycle.
    from primestone.storytelling.retention import analyze

    return analyze(script, curve)
