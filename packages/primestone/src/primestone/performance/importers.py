"""Entrées GRATUITES des performances de la chaîne Primestone.

1. Export CSV de YouTube Studio (Analytics → Avancé → Exporter) : aucun accès API requis.
   Les en-têtes dépendent de la langue de l'interface : synonymes FR/EN reconnus, colonnes
   inconnues IGNORÉES et signalées (jamais devinées).
2. YouTube Analytics API v2 (OAuth de la chaîne, lecture seule, gratuite) : client fourni,
   jeton d'accès injecté (jamais journalisé).
"""

from __future__ import annotations

import contextlib
import csv
import io
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from primestone.forensic import fold

# En-tête normalisé (fold) → (champ, conversion). Synonymes FR/EN de YouTube Studio.
_ID = ("contenu", "content", "video", "id de la video", "video id")
_TITLE = ("titre de la video", "video title", "titre", "title")
_PUBLISHED = ("heure de publication de la video", "video publish time", "date de publication")
_DURATION = ("duree", "duration")
_METRICS: dict[str, tuple[str, ...]] = {
    "views": ("vues", "views"),
    "impressions": ("impressions",),
    "ctr": ("taux de clics des impressions (%)", "impressions click-through rate (%)"),
    "avg_view_duration_s": ("duree moyenne de visionnage", "average view duration"),
    "avg_view_percentage": (
        "pourcentage moyen regarde (%)",
        "average percentage viewed (%)",
    ),
    "watch_time_min": ("duree de visionnage (heures)", "watch time (hours)"),
    "likes": ("j'aime", "likes"),
    "comments": ("commentaires ajoutes", "comments added"),
    "subscribers_gained": ("abonnes gagnes", "subscribers gained", "abonnes", "subscribers"),
}


class ImportError_(ValueError):
    """Fichier ou réponse illisible (nom distinct de l'exception native ImportError)."""


def _number(raw: str) -> Decimal | None:
    raw = raw.strip().replace("\u202f", "").replace("\xa0", "").replace(" ", "")
    if not raw or raw in ("-", "—"):
        return None
    if raw.count(":") in (1, 2):  # durée h:mm:ss ou m:ss → secondes
        parts = [int(p) for p in raw.split(":")]
        seconds = 0
        for p in parts:
            seconds = seconds * 60 + p
        return Decimal(seconds)
    if "," in raw and "." not in raw:
        raw = raw.replace(",", ".")
    try:
        return Decimal(raw.replace(",", "").rstrip("%"))
    except InvalidOperation:
        return None


def parse_studio_csv(content: str) -> dict[str, Any]:
    """→ {"rows": [{external_id, title, published_at, metrics}], "ignored_columns": [...]}"""
    reader = csv.reader(io.StringIO(content.lstrip("﻿")))
    try:
        header = next(reader)
    except StopIteration:
        raise ImportError_("fichier vide") from None
    folded = [fold(h) for h in header]

    def column(names: tuple[str, ...]) -> int | None:
        return next((i for i, h in enumerate(folded) if h in {fold(n) for n in names}), None)

    id_col, title_col = column(_ID), column(_TITLE)
    if id_col is None:
        raise ImportError_("colonne d'identifiant de vidéo introuvable (« Contenu » / « Content »)")
    metric_cols = {m: column(names) for m, names in _METRICS.items()}
    used = {id_col, title_col, column(_PUBLISHED), column(_DURATION), *metric_cols.values()}
    ignored = [header[i] for i in range(len(header)) if i not in used]
    rows = []
    for line in reader:
        if not line or len(line) <= id_col:
            continue
        external_id = line[id_col].strip()
        if not external_id or fold(external_id) in ("total", "totaux"):
            continue  # ligne de total de l'export
        metrics: dict[str, Decimal] = {}
        for metric, idx in metric_cols.items():
            if idx is not None and idx < len(line):
                value = _number(line[idx])
                if value is not None:
                    # Studio exporte la durée de visionnage en heures : stockée en minutes.
                    metrics[metric] = value * 60 if metric == "watch_time_min" else value
        published = None
        pub_col = column(_PUBLISHED)
        if pub_col is not None and pub_col < len(line) and line[pub_col].strip():
            for fmt in ("%b %d, %Y", "%d %b %Y", "%Y-%m-%d"):
                with contextlib.suppress(ValueError):
                    published = datetime.strptime(line[pub_col].strip(), fmt).date()
                    break
        rows.append(
            {
                "external_id": external_id,
                "title": line[title_col].strip() if title_col is not None else external_id,
                "published_on": published,
                "metrics": metrics,
            }
        )
    return {"rows": rows, "ignored_columns": ignored}


ANALYTICS_API = "https://youtubeanalytics.googleapis.com/v2/reports"
_API_METRICS = {
    "views": "views",
    "estimatedMinutesWatched": "watch_time_min",
    "averageViewDuration": "avg_view_duration_s",
    "averageViewPercentage": "avg_view_percentage",
    "likes": "likes",
    "comments": "comments",
    "subscribersGained": "subscribers_gained",
}


class AnalyticsClient:
    """YouTube Analytics API v2, chaîne du propriétaire (ids=channel==MINE), lecture seule."""

    def __init__(
        self, token: Callable[[], str], *, transport: httpx.BaseTransport | None = None
    ) -> None:
        self._token = token
        self._client = httpx.Client(timeout=30, transport=transport)

    def video_report(
        self, start: date, end: date, *, max_results: int = 200
    ) -> list[dict[str, Any]]:
        response = self._client.get(
            ANALYTICS_API,
            params={
                "ids": "channel==MINE",
                "startDate": start.isoformat(),
                "endDate": end.isoformat(),
                "metrics": ",".join(_API_METRICS),
                "dimensions": "video",
                "sort": "-views",
                "maxResults": max_results,
            },
            headers={"authorization": f"Bearer {self._token()}"},
        )
        if response.status_code != 200:
            raise ImportError_(
                f"YouTube Analytics a refusé la requête (HTTP {response.status_code})"
            )
        data = response.json()
        names = [h["name"] for h in data.get("columnHeaders", [])]
        rows = []
        for raw in data.get("rows", []):
            record = dict(zip(names, raw, strict=False))
            rows.append(
                {
                    "external_id": record["video"],
                    "title": record["video"],
                    "published_on": None,
                    "metrics": {
                        ours: Decimal(str(record[theirs]))
                        for theirs, ours in _API_METRICS.items()
                        if record.get(theirs) is not None
                    },
                }
            )
        return rows

    def close(self) -> None:
        self._client.close()
