"""Évaluer chaque contenu selon SON objectif (méthode `objective-kpi@1`).

Une vidéo de découverte, une enquête et une vidéo communautaire n'ont pas les mêmes buts :
chacune est comparée à la médiane des contenus de MÊME objectif (et même format si connu),
sur les indicateurs propres à cet objectif. Les vues seules ne jugent jamais un contenu.
"""

from __future__ import annotations

from collections.abc import Sequence
from statistics import median
from typing import Any

METHOD = "objective-kpi@1"
OBJECTIVE_KPIS: dict[str, tuple[str, ...]] = {
    # Faire découvrir la chaîne : être choisi, attirer de nouveaux spectateurs, convertir.
    "DISCOVERY": ("ctr", "new_viewers", "subscribers_gained", "avg_view_percentage"),
    # Expliquer un univers : être regardé longtemps.
    "EXPLORATION": ("avg_view_percentage", "watch_time_min", "avg_view_duration_s", "shares"),
    # Analyse avancée : fidéliser les connaisseurs, susciter des échanges argumentés.
    "EXPERTISE": ("avg_view_percentage", "returning_viewers", "comments", "saves"),
    # Communauté : interactions et retour des habitués.
    "COMMUNITY": ("comments", "shares", "returning_viewers", "likes"),
}
MIN_PEERS = 3  # en dessous : pas de comparaison (repère trop fragile)


def evaluate(contents: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """`contents` : {id, title, objective, format, metrics}. Contenus sans objectif : listés,
    non évalués (on ne devine pas l'intention d'une vidéo)."""
    results, unclassified = [], []
    for c in contents:
        objective = c.get("objective")
        if objective not in OBJECTIVE_KPIS:
            unclassified.append(c["title"])
            continue
        peers = [
            p
            for p in contents
            if p.get("objective") == objective
            and (not c.get("format") or p.get("format") == c.get("format"))
        ]
        kpis: dict[str, dict[str, Any]] = {}
        for kpi in OBJECTIVE_KPIS[objective]:
            values = [p["metrics"][kpi] for p in peers if kpi in p["metrics"]]
            value = c["metrics"].get(kpi)
            if value is None:
                kpis[kpi] = {"value": None, "status": "NON FOURNI"}
            elif len(values) < MIN_PEERS:
                kpis[kpi] = {"value": value, "status": "REPÈRE INSUFFISANT", "peers": len(values)}
            else:
                ref = median(values)
                ratio = round(value / ref, 2) if ref else None
                kpis[kpi] = {
                    "value": value,
                    "peer_median": ref,
                    "ratio": ratio,
                    "status": "AU-DESSUS"
                    if ratio and ratio >= 1.1
                    else "EN DESSOUS"
                    if ratio is not None and ratio <= 0.9
                    else "DANS LA NORME",
                    "peers": len(values),
                }
        results.append(
            {
                "id": c["id"],
                "title": c["title"],
                "objective": objective,
                "format": c.get("format"),
                "kpis": kpis,
                "evidence": "OBSERVED",
            }
        )
    return {
        "method": METHOD,
        "data_class": "PRIVATE_AUTHORIZED",
        "objectives": {k: list(v) for k, v in OBJECTIVE_KPIS.items()},
        "evaluations": results,
        "unclassified": unclassified,
        "note": "Observations comparées aux contenus de même objectif ; ni causes, ni prédictions.",
    }
