"""Connecteurs de collecte GRATUITS. Chacun renvoie des enregistrements normalisés :

    {"platform", "external_id", "url", "title", "description", "channel", "language",
     "published_at", "metrics": {"views"?, "likes"?, "comments"?}}

Seules des métriques PUBLIQUES sont lues (compteurs affichés par la plateforme). Aucune
métrique privée (CTR, rétention, impressions) n'est jamais demandée ni estimée.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from xml.etree import ElementTree

import httpx

PUBLIC_METRICS = ("views", "likes", "comments")
YOUTUBE_API = "https://www.googleapis.com/youtube/v3"
# Coût en unités de quota (documentation officielle YouTube Data API v3).
SEARCH_UNITS = 100
VIDEOS_UNITS = 1


class ConnectorError(RuntimeError):
    pass


def language_of(code: str | None, fallback: str) -> str:
    """« fr-FR » → fr ; « en-US » → en ; autre ou inconnu → langue de repli."""
    prefix = (code or "").split("-")[0].lower()
    return prefix if prefix in ("fr", "en") else fallback


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        pass
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


# --- RSS / Atom -------------------------------------------------------------------------------

_ATOM = "{http://www.w3.org/2005/Atom}"


def parse_feed(xml: str | bytes, *, language: str, platform: str = "rss") -> list[dict[str, Any]]:
    """Analyse un flux RSS 2.0 ou Atom (sans entités externes : bibliothèque standard)."""
    if isinstance(xml, str):
        xml = xml.encode()
    if b"<!DOCTYPE" in xml[:2000] or b"<!ENTITY" in xml[:2000]:
        raise ConnectorError("flux refusé : déclaration DOCTYPE/ENTITY")
    try:
        root = ElementTree.fromstring(xml)  # noqa: S314 - DOCTYPE/ENTITY refusés ci-dessus
    except ElementTree.ParseError as exc:
        raise ConnectorError(f"flux illisible : {exc}") from None
    records: list[dict[str, Any]] = []
    if root.tag == f"{_ATOM}feed":
        feed_lang = root.get("{http://www.w3.org/XML/1998/namespace}lang")
        for entry in root.findall(f"{_ATOM}entry"):
            link = entry.find(f"{_ATOM}link")
            url = link.get("href") if link is not None else None
            ident = entry.findtext(f"{_ATOM}id") or url
            title = (entry.findtext(f"{_ATOM}title") or "").strip()
            if not ident or not title:
                continue
            author = entry.find(f"{_ATOM}author")
            records.append(
                {
                    "platform": platform,
                    "external_id": ident.strip(),
                    "url": url,
                    "title": title,
                    "description": (entry.findtext(f"{_ATOM}summary") or "").strip() or None,
                    "channel": author.findtext(f"{_ATOM}name") if author is not None else None,
                    "language": language_of(feed_lang, language),
                    "published_at": _parse_date(
                        entry.findtext(f"{_ATOM}published") or entry.findtext(f"{_ATOM}updated")
                    ),
                    "metrics": {},
                }
            )
        return records
    channel = root.find("channel")
    if channel is None:
        raise ConnectorError("flux non reconnu (ni RSS 2.0 ni Atom)")
    feed_lang = channel.findtext("language")
    channel_title = channel.findtext("title")
    for item in channel.findall("item"):
        url = item.findtext("link")
        ident = item.findtext("guid") or url
        title = (item.findtext("title") or "").strip()
        if not ident or not title:
            continue
        records.append(
            {
                "platform": platform,
                "external_id": ident.strip(),
                "url": url,
                "title": title,
                "description": (item.findtext("description") or "").strip() or None,
                "channel": channel_title,
                "language": language_of(feed_lang, language),
                "published_at": _parse_date(item.findtext("pubDate")),
                "metrics": {},
            }
        )
    return records


def fetch_feed(url: str, *, timeout: float, transport: httpx.BaseTransport | None = None) -> bytes:
    if not url.startswith("https://"):
        raise ConnectorError("seuls les flux HTTPS sont acceptés")
    with httpx.Client(timeout=timeout, transport=transport, follow_redirects=True) as client:
        response = client.get(url, headers={"user-agent": "primestone-market/1.0"})
    if response.status_code != 200:
        raise ConnectorError(f"flux indisponible (HTTP {response.status_code})")
    if len(response.content) > 5_000_000:
        raise ConnectorError("flux trop volumineux (> 5 Mo)")
    return response.content


# --- YouTube Data API v3 (gratuite sous quota) -------------------------------------------------


class YouTubeClient:
    """Recherche publique + statistiques publiques. Compte les unités de quota consommées."""

    def __init__(
        self,
        api_key: str,
        *,
        timeout: float = 20.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise ConnectorError("clé YouTube Data API absente")
        self._key = api_key
        self._client = httpx.Client(base_url=YOUTUBE_API, timeout=timeout, transport=transport)
        self.units = 0

    def _get(self, path: str, params: dict[str, Any], units: int) -> dict[str, Any]:
        self.units += units
        response = self._client.get(path, params={**params, "key": self._key})
        if response.status_code != 200:
            # Le message d'erreur ne contient jamais la clé (paramètres non recopiés).
            reason = ""
            with contextlib.suppress(ValueError, KeyError, IndexError, TypeError):
                reason = response.json()["error"]["errors"][0]["reason"]
            raise ConnectorError(
                f"YouTube a refusé la requête (HTTP {response.status_code} {reason})"
            )
        data: dict[str, Any] = response.json()
        return data

    def search(
        self,
        query: str,
        *,
        language: str,
        max_results: int = 25,
        published_after: datetime | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": max(1, min(max_results, 50)),
            "relevanceLanguage": language,
            "order": "relevance",
        }
        if published_after:
            params["publishedAfter"] = published_after.astimezone(UTC).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
        found = self._get("/search", params, SEARCH_UNITS)
        ids = [i["id"]["videoId"] for i in found.get("items", []) if i.get("id", {}).get("videoId")]
        return self.videos(ids, language=language)

    def videos(self, ids: Sequence[str], *, language: str) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for start in range(0, len(ids), 50):
            chunk = list(ids[start : start + 50])
            data = self._get(
                "/videos", {"part": "snippet,statistics", "id": ",".join(chunk)}, VIDEOS_UNITS
            )
            for video in data.get("items", []):
                snippet, stats = video.get("snippet", {}), video.get("statistics", {})
                metrics = {
                    name: int(stats[key])
                    for name, key in (
                        ("views", "viewCount"),
                        ("likes", "likeCount"),
                        ("comments", "commentCount"),
                    )
                    if str(stats.get(key, "")).isdigit()  # compteurs masqués : absents, jamais 0
                }
                records.append(
                    {
                        "platform": "youtube",
                        "external_id": video["id"],
                        "url": f"https://www.youtube.com/watch?v={video['id']}",
                        "title": snippet.get("title", "").strip(),
                        "description": (snippet.get("description") or "")[:2000] or None,
                        "channel": snippet.get("channelTitle"),
                        "language": language_of(
                            snippet.get("defaultAudioLanguage") or snippet.get("defaultLanguage"),
                            language,
                        ),
                        "published_at": _parse_date(snippet.get("publishedAt")),
                        "metrics": metrics,
                    }
                )
        return records

    def close(self) -> None:
        self._client.close()


YouTubeFactory = Callable[[], YouTubeClient]
