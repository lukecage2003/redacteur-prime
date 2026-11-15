"""Content Opportunity Engine (méthode `opportunity@1`).

Pour chaque sujet suivi, croise : popularité anglophone, demande francophone OBSERVÉE (jamais
déduite de la popularité anglophone), concurrence francophone, demande de la communauté,
audiences liées, preuves documentaires disponibles (pages transcrites), potentiel
d'originalité (théories à l'étude), faisabilité.

Score = moyenne pondérée des SEULES composantes mesurées ; une composante sans données est
exclue et signalée. Confiance = part du poids réellement mesuré (HIGH ≥ 0,75, MEDIUM ≥ 0,5,
sinon LOW). Sans demande francophone observée, l'opportunité est marquée HYPOTHÈSE.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

METHOD = "opportunity@1"
WEIGHTS = {
    "fr_gap": 0.25,  # demande EN x (1 - saturation FR) : écart de l'offre
    "fr_demand": 0.20,  # demande FR observée (vues FR mesurées ou demandes de la communauté)
    "community": 0.15,  # questions / demandes récurrentes sur le sujet
    "documentation": 0.20,  # pages transcrites disponibles comme preuves
    "originality": 0.10,  # théories / contradictions à instruire : angle propre
    "audience": 0.10,  # segments confirmés liés au sujet
}


def _clip(value: float) -> float:
    return max(0.0, min(1.0, value))


def score_topic(signals: dict[str, Any]) -> dict[str, Any]:
    """`signals` : mesures brutes d'un sujet (None = non mesuré)."""
    components: dict[str, float | None] = {
        "fr_gap": signals.get("gap_score"),
        "fr_demand": None,
        "community": None,
        "documentation": None,
        "originality": None,
        "audience": None,
    }
    fr_views, requests = signals.get("fr_median_views"), signals.get("community_requests", 0)
    if fr_views is not None or requests:
        # Demande FR observée : vues FR mesurées (log, plafonné à 100 000) et/ou demandes.
        from math import log10

        views_part = _clip(log10(1 + fr_views) / 5) if fr_views is not None else 0.0
        components["fr_demand"] = round(max(views_part, _clip(requests / 10)), 3)
    if signals.get("community_measured"):
        components["community"] = round(
            _clip((requests + signals.get("community_questions", 0)) / 15), 3
        )
    if signals.get("pages") is not None:
        components["documentation"] = round(_clip(signals["pages"] / 10), 3)
    if signals.get("theories") is not None:
        components["originality"] = round(_clip(signals["theories"] / 3), 3)
    if signals.get("segments") is not None:
        confirmed = sum(1 for s in signals["segments"] if s["status"] == "CONFIRMED")
        components["audience"] = round(_clip(confirmed / 2), 3) if signals["segments"] else 0.0
    measured = {k: v for k, v in components.items() if v is not None}
    weight = sum(WEIGHTS[k] for k in measured)
    score = round(sum(WEIGHTS[k] * v for k, v in measured.items()) / weight, 3) if weight else None
    confidence = "HIGH" if weight >= 0.75 else "MEDIUM" if weight >= 0.5 else "LOW"
    return {
        "score": score,
        "components": components,
        "measured_weight": round(weight, 2),
        "confidence": confidence,
        "missing": [k for k, v in components.items() if v is None],
        "fr_demand_observed": components["fr_demand"] is not None,
    }


def formats_for(segments: Sequence[dict[str, Any]]) -> list[str]:
    levels = {s.get("knowledge_level") for s in segments}
    formats = []
    if not levels or "NOVICE" in levels or None in levels:
        formats.append("DISCOVERY : Short / Reel / TikTok (contexte minimal, un fait fort)")
    if not levels or "INTERMEDIATE" in levels or None in levels:
        formats.append("EXPLORATION : vidéo longue 12-20 min en chapitres + carrousel")
    if "EXPERT" in levels or not levels:
        formats.append("EXPERTISE : enquête longue (preuves et contre-preuves) + dossier écrit")
    return formats


def build(topic: dict[str, Any], signals: dict[str, Any]) -> dict[str, Any]:
    scored = score_topic(signals)
    risks = []
    if not scored["fr_demand_observed"]:
        risks.append("demande francophone NON observée : la popularité anglophone ne la prouve pas")
    if signals.get("pages") in (None, 0):
        risks.append("aucune page transcrite sur ce sujet : preuves à constituer avant d'écrire")
    if signals.get("controversies"):
        risks.append(
            f"{signals['controversies']} commentaire(s) contestataire(s) : vérifier les sources"
        )
    if scored["confidence"] == "LOW":
        risks.append("confiance faible : moins de la moitié des critères mesurés")
    angle = []
    if signals.get("theories"):
        angle.append(f"{signals['theories']} théorie(s) à l'étude au laboratoire (angle original)")
    if signals.get("gap_score"):
        angle.append(f"écart EN→FR {signals['gap_score']} : sujet peu traité en français")
    need = []
    if signals.get("community_requests"):
        need.append(f"{signals['community_requests']} demande(s) explicite(s) de la communauté")
    if signals.get("community_questions"):
        need.append(f"{signals['community_questions']} question(s) de la communauté")
    segments = signals.get("segments") or []
    recommendation = (
        "PRIORISER"
        if scored["score"] is not None and scored["score"] >= 0.6 and scored["fr_demand_observed"]
        else "EXPLORER (tester par un format court)"
        if scored["score"] is not None and scored["score"] >= 0.4
        else "SURVEILLER"
    )
    return {
        "topic": topic["name"],
        "topic_id": topic["id"],
        "status": "OPPORTUNITY" if scored["fr_demand_observed"] else "HYPOTHESIS",
        "potential_audience": [f"{s['name']} ({s['status']})" for s in segments]
        or ["non lié à un segment"],
        "need": need or ["aucun besoin exprimé mesuré"],
        "angle": angle or ["à définir"],
        "evidence": {"pages": signals.get("pages"), "examples": signals.get("examples", [])},
        "competition": {
            "fr_items": signals.get("fr_items"),
            "fr_channels": signals.get("fr_channels", []),
        },
        "risks": risks,
        "formats": formats_for(segments),
        "recommendation": recommendation,
        **scored,
        "data_class": "ESTIMATE",
    }
