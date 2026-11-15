"""Expériences structurées (méthode `ab-proportion@1`).

Un gagnant n'est déclaré que si : 2 variantes ou plus avec des COMPTES (exposition, succès),
au moins `MIN_EXPOSURES` expositions et `MIN_SUCCESSES` succès par variante, et une différence
significative au seuil `ALPHA` (test bilatéral de deux proportions). Sinon : INCONCLUSIVE, avec
la raison. Une part rapportée sans comptes (ex. « Tester et comparer » de YouTube) est
enregistrée comme verdict de la plateforme, jamais comme démonstration.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

METHOD = "ab-proportion@1"
MIN_EXPOSURES = 1000
MIN_SUCCESSES = 30
ALPHA = 0.05
Z = 1.959964  # quantile 97,5 % de la loi normale


def wilson(successes: int, n: int) -> tuple[float, float]:
    """Intervalle de confiance de Wilson à 95 % d'une proportion."""
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + Z**2 / n
    centre = (p + Z**2 / (2 * n)) / denom
    half = Z * math.sqrt(p * (1 - p) / n + Z**2 / (4 * n**2)) / denom
    return (round(max(0.0, centre - half), 5), round(min(1.0, centre + half), 5))


def two_proportion_p_value(s1: int, n1: int, s2: int, n2: int) -> float:
    pooled = (s1 + s2) / (n1 + n2)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    if se == 0:
        return 1.0
    z = abs(s1 / n1 - s2 / n2) / se
    return round(math.erfc(z / math.sqrt(2)), 6)


def decide(variants: Sequence[dict[str, Any]]) -> dict[str, Any]:
    counted = [v for v in variants if v.get("exposures") is not None]
    platform = [
        {"label": v["label"], "reported_share": v["reported_share"], "source": v["source"]}
        for v in variants
        if v.get("reported_share") is not None
    ]
    base: dict[str, Any] = {
        "method": METHOD,
        "thresholds": {
            "min_exposures": MIN_EXPOSURES,
            "min_successes": MIN_SUCCESSES,
            "alpha": ALPHA,
        },
        "platform_reported": platform,
    }
    if len(counted) < 2:
        reason = "moins de deux variantes avec des comptes (exposition, succès)"
        if platform:
            reason += " ; part rapportée par la plateforme notée, non démontrée ici"
        return {**base, "status": "INCONCLUSIVE", "winner": None, "reason": reason}
    rows = []
    for v in counted:
        n, s = int(v["exposures"]), int(v["successes"])
        rows.append(
            {
                "label": v["label"],
                "exposures": n,
                "successes": s,
                "rate": round(s / n, 5) if n else 0.0,
                "ci95": wilson(s, n),
            }
        )
    thin = [
        r["label"] for r in rows if r["exposures"] < MIN_EXPOSURES or r["successes"] < MIN_SUCCESSES
    ]
    best, second = sorted(rows, key=lambda r: -r["rate"])[:2]
    p_value = two_proportion_p_value(
        best["successes"], best["exposures"], second["successes"], second["exposures"]
    )
    result = {**base, "variants": rows, "p_value": p_value}
    if thin:
        return {
            **result,
            "status": "INCONCLUSIVE",
            "winner": None,
            "reason": f"échantillon insuffisant pour : {', '.join(thin)}",
        }
    if p_value >= ALPHA:
        return {
            **result,
            "status": "INCONCLUSIVE",
            "winner": None,
            "reason": f"différence non significative (p = {p_value} ≥ {ALPHA})",
        }
    lift = round(best["rate"] / second["rate"] - 1, 4) if second["rate"] else None
    return {
        **result,
        "status": "CONCLUDED",
        "winner": best["label"],
        "relative_lift": lift,
        "reason": f"différence significative (p = {p_value} < {ALPHA}) dans ce contexte uniquement",
    }
