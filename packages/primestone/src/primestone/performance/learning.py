"""Boucle mesurer → apprendre → optimiser (méthode `perf-learn@1`), sur les SEULS contenus de
Primestone.

- Repères de la chaîne : médiane de chaque métrique ; chaque contenu est situé au-dessus ou en
  dessous (rapport à la médiane).
- Signaux : corrélation de rang (Spearman) entre chaque critère de la note du script (phase 10)
  et la rétention (pourcentage moyen regardé) ou le CTR. Exige au moins `min_items` contenus
  reliés à un script noté, sinon INSUFFICIENT_DATA.
- Prudence explicite : corrélation ≠ causalité ; petit échantillon ; signaux à confirmer.
"""

from __future__ import annotations

from collections.abc import Sequence
from statistics import median
from typing import Any

METHOD = "perf-learn@1"
TARGETS = ("avg_view_percentage", "ctr")


def _ranks(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1  # rangs moyens en cas d'égalité
        i = j + 1
    return ranks


def spearman(x: Sequence[float], y: Sequence[float]) -> float | None:
    if len(x) != len(y) or len(x) < 3:
        return None
    rx, ry = _ranks(x), _ranks(y)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    vx = sum((a - mx) ** 2 for a in rx)
    vy = sum((b - my) ** 2 for b in ry)
    if not vx or not vy:
        return None
    return round(float(cov / (vx * vy) ** 0.5), 3)


def learn(contents: Sequence[dict[str, Any]], *, min_items: int = 5) -> dict[str, Any]:
    """`contents` : {title, metrics: {nom: float}, script_criteria: {critère: score} | None}."""
    metrics = sorted({m for c in contents for m in c["metrics"]})
    benchmarks = {
        m: median([c["metrics"][m] for c in contents if m in c["metrics"]]) for m in metrics
    }
    positions = []
    for c in contents:
        relative = {
            m: round(v / benchmarks[m], 2) if benchmarks[m] else None
            for m, v in c["metrics"].items()
        }
        positions.append({"title": c["title"], "relative_to_median": relative})
    linked = [c for c in contents if c.get("script_criteria")]
    signals: list[dict[str, Any]] = []
    status = "INSUFFICIENT_DATA" if len(linked) < min_items else "OK"
    if status == "OK":
        criteria = sorted({k for c in linked for k in c["script_criteria"]})
        for target in TARGETS:
            sample = [c for c in linked if target in c["metrics"]]
            if len(sample) < min_items:
                continue
            for criterion in criteria:
                pairs = [
                    (c["script_criteria"][criterion], c["metrics"][target])
                    for c in sample
                    if criterion in c["script_criteria"]
                ]
                rho = spearman([p[0] for p in pairs], [p[1] for p in pairs])
                if rho is not None:
                    signals.append(
                        {"criterion": criterion, "target": target, "rho": rho, "n": len(pairs)}
                    )
        signals.sort(key=lambda s: -abs(s["rho"]))
    recommendations = [
        f"« {s['criterion']} » semble lié à « {s['target']} » (rho {s['rho']:+.2f}, "
        f"n = {s['n']}) : {'à renforcer' if s['rho'] > 0 else 'à réexaminer'} "
        "dans les prochains scripts — signal, pas preuve."
        for s in signals
        if abs(s["rho"]) >= 0.5
    ]
    return {
        "method": METHOD,
        "data_class": "PRIVATE_AUTHORIZED",
        "contents": len(contents),
        "linked_to_scored_script": len(linked),
        "min_items": min_items,
        "status": status,
        "benchmarks": benchmarks,
        "positions": positions,
        "signals": signals,
        "recommendations": recommendations,
        "caveat": "Corrélation ≠ causalité ; petit échantillon ; uniquement la chaîne Primestone.",
    }
