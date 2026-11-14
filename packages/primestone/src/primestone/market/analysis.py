"""Analyse de marché transparente (méthode `market-gap@1`), sur données PUBLIQUES collectées.

Pour chaque sujet et chaque langue, dans la fenêtre d'analyse :
- offre n = nombre de contenus collectés qui parlent du sujet (mot-clé dans titre/description) ;
- demande = médiane des vues publiques (dernier relevé de chaque contenu) ; exige au moins
  `min_items` contenus avec des vues, sinon INSUFFICIENT_DATA (jamais d'extrapolation) ;
- demande EN normalisée = log10(1 + médiane EN) / log10(1 + plus forte médiane EN observée) ;
- saturation FR = min(1, n_FR / n_EN) : l'offre francophone relative à l'offre anglophone ;
- score d'écart EN→FR = demande EN normalisée x (1 - saturation FR) ;
- différence culturelle = log10((1 + médiane FR) / (1 + médiane EN)) quand les deux sont
  mesurées : > 0 le sujet marche relativement mieux en français.
Tous les résultats sont des ESTIMATIONS calculées sur un ÉCHANTILLON collecté, pas sur toute la
plateforme ; chaque chiffre renvoie à ses contenus sources (classe PUBLIC).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import median
from typing import Any

from primestone.forensic import fold

METHOD = "market-gap@1"
LANGUAGES = ("fr", "en")


@dataclass(frozen=True)
class Item:
    id: str
    language: str
    title: str
    description: str | None
    url: str | None
    channel: str | None
    published_at: datetime | None
    first_seen_at: datetime
    views: int | None
    observed_at: datetime | None


@dataclass(frozen=True)
class Topic:
    id: str
    name: str
    keywords: tuple[str, ...]


def matches(topic: Topic, item: Item) -> bool:
    text = f" {fold(f'{item.title} {item.description or ""}')} "
    return any(f" {fold(k)} " in text for k in topic.keywords if fold(k))


def _lang_stats(items: Sequence[Item], min_items: int) -> dict[str, Any]:
    views = [i.views for i in items if i.views is not None]
    top = sorted(items, key=lambda i: i.views or -1, reverse=True)[:5]
    return {
        "items": len(items),
        "items_with_views": len(views),
        "median_views": median(views) if len(views) >= min_items else None,
        "sufficient": len(views) >= min_items,
        "sources": [
            {
                "title": i.title,
                "url": i.url,
                "channel": i.channel,
                "views": i.views,
                "observed_at": i.observed_at,
                "data_class": "PUBLIC",
            }
            for i in top
        ],
    }


def analyze(
    items: Sequence[Item],
    topics: Sequence[Topic],
    *,
    now: datetime,
    window_days: int = 90,
    min_items: int = 5,
) -> dict[str, Any]:
    since = now - timedelta(days=window_days)
    recent = [i for i in items if (i.published_at or i.first_seen_at) >= since]
    rows: list[dict[str, Any]] = []
    for topic in topics:
        per_lang = {
            lang: _lang_stats(
                [i for i in recent if i.language == lang and matches(topic, i)], min_items
            )
            for lang in LANGUAGES
        }
        rows.append({"topic": topic.name, "topic_id": topic.id, "languages": per_lang})

    en_medians = [r["languages"]["en"]["median_views"] for r in rows]
    top_en = max((m for m in en_medians if m is not None), default=None)
    for r in rows:
        fr, en = r["languages"]["fr"], r["languages"]["en"]
        notes: list[str] = []
        if not en["sufficient"] or not top_en:
            r.update(status="INSUFFICIENT_DATA", gap_score=None, demand_en=None)
            r["saturation_fr"] = None
            notes.append(
                f"{en['items_with_views']} contenu(s) anglophone(s) avec vues "
                f"(minimum {min_items}) : pas de score"
            )
        else:
            demand = math.log10(1 + en["median_views"]) / math.log10(1 + top_en)
            saturation = min(1.0, fr["items"] / en["items"])
            r.update(
                status="SCORED",
                demand_en=round(demand, 3),
                saturation_fr=round(saturation, 3),
                gap_score=round(demand * (1 - saturation), 3),
            )
            notes.append(
                f"demande EN = log10(1 + {en['median_views']:g}) / log10(1 + {top_en:g}) "
                f"= {demand:.3f}"
            )
            notes.append(
                f"saturation FR = min(1, {fr['items']} / {en['items']}) = {saturation:.3f}"
            )
            notes.append(f"écart = {demand:.3f} x (1 - {saturation:.3f}) = {r['gap_score']}")
        if fr["sufficient"] and en["sufficient"]:
            r["cultural_difference"] = round(
                math.log10((1 + fr["median_views"]) / (1 + en["median_views"])), 3
            )
        else:
            r["cultural_difference"] = None
        r["explanation"] = notes
        r["data_class"] = "ESTIMATE"

    scored = [r for r in rows if r["status"] == "SCORED"]
    supply = sorted(r["languages"]["en"]["items"] for r in scored)
    typical_supply = median(supply) if supply else 0
    return {
        "method": METHOD,
        "data_class": "ESTIMATE",
        "window_days": window_days,
        "min_items": min_items,
        "generated_at": now,
        "caveat": (
            "Échantillon collecté (recherches et flux choisis), pas l'exhaustivité des "
            "plateformes ; vues publiques uniquement ; aucune métrique privée de concurrent."
        ),
        "items_considered": len(recent),
        "topics": sorted(rows, key=lambda r: (r["gap_score"] is None, -(r["gap_score"] or 0))),
        "opportunities": [
            r["topic"] for r in sorted(scored, key=lambda r: -r["gap_score"]) if r["gap_score"] > 0
        ],
        "popular": [r["topic"] for r in sorted(scored, key=lambda r: -r["demand_en"])],
        "niches": [
            r["topic"]
            for r in scored
            # Niche : offre anglophone sous la médiane des sujets, demande forte (≥ 3 sujets).
            if len(scored) >= 3
            and r["languages"]["en"]["items"] < typical_supply
            and r["demand_en"] >= 0.5
        ],
        "saturated_fr": [r["topic"] for r in scored if r["saturation_fr"] >= 1.0],
    }
