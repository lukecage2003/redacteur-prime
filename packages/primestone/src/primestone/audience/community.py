"""Community Intelligence : commentaires PUBLICS de la chaîne du propriétaire, classés et
regroupés sans jamais conserver l'identité de leurs auteurs (méthode `community@1`).

Le moteur PROPOSE (sondages, vidéos réponses, débats, séries) ; il ne publie, ne répond et ne
« like » jamais rien : aucune interaction automatisée.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Sequence
from typing import Any

import httpx

from primestone.forensic import fold
from primestone.market.connectors import YOUTUBE_API, ConnectorError, language_of

METHOD = "community@1"
_QUESTION_START = re.compile(
    r"^(pourquoi|comment|qui|quand|quel|quelle|quels|est-ce|est ce|why|how|who|when|what|"
    r"which|is|are|does|do|can)\b"
)
_KIND_MARKERS = {
    "REQUEST": (
        "fais une video",
        "tu pourrais",
        "tu peux parler",
        "une video sur",
        "please make",
        "can you do",
        "could you make",
        "video about",
        "next video",
    ),
    "THEORY": ("theorie", "je pense que", "et si", "ma theorie", "theory", "i think", "what if"),
    "CONTROVERSY": (
        "faux",
        "n'importe quoi",
        "pas d'accord",
        "erreur",
        "wrong",
        "disagree",
        "not true",
        "nonsense",
    ),
    "PRAISE": ("merci", "genial", "super video", "excellent", "thank you", "great video", "love"),
}
_STOP_WORDS = (
    "le la les un une des de du et a en que qui est il elle on ce se sa son pour pas plus "
    "dans par sur au aux ne je tu vous the of and to in is it that was for on with as this "
    "be at by are an video videos"
)
_STOP = set(_STOP_WORDS.split())
MIN_RECURRENCE = 3  # une question n'est « récurrente » qu'à partir de 3 commentaires distincts


def classify(text: str) -> str:
    folded = fold(text)
    for kind in ("REQUEST", "THEORY", "CONTROVERSY"):
        if any(m in folded for m in _KIND_MARKERS[kind]):
            return kind
    if "?" in text or _QUESTION_START.match(folded):
        return "QUESTION"
    if any(m in folded for m in _KIND_MARKERS["PRAISE"]):
        return "PRAISE"
    return "OTHER"


def _terms(text: str, names: Sequence[str]) -> set[str]:
    folded = f" {fold(text)} "
    mentioned = {n for n in names if f" {fold(n)} " in folded}
    return mentioned or {w for w in folded.split() if len(w) > 4 and w not in _STOP}


def insights(comments: Sequence[dict[str, Any]], known_names: Sequence[str] = ()) -> dict[str, Any]:
    """Regroupe par nature et par sujet (personnage connu ou mot-clé) ; propose des actions."""
    by_kind = Counter(c["kind"] for c in comments)
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for c in comments:
        for term in _terms(c["text"], known_names):
            groups[(c["kind"], term)].append(c)
    recurring = sorted(
        (
            {
                "kind": kind,
                "subject": term,
                "count": len(items),
                "likes": sum(i.get("like_count", 0) for i in items),
                "examples": [i["text"][:200] for i in items[:3]],
            }
            for (kind, term), items in groups.items()
            if len(items) >= MIN_RECURRENCE
            and kind in ("QUESTION", "REQUEST", "THEORY", "CONTROVERSY")
        ),
        key=lambda g: (-g["count"], -g["likes"]),
    )
    proposals = []
    for g in recurring:
        if g["kind"] == "QUESTION":
            proposals.append(f"Vidéo réponse ou FAQ : « {g['subject']} » ({g['count']} questions).")
        elif g["kind"] == "REQUEST":
            proposals.append(
                f"Sujet demandé : « {g['subject']} » ({g['count']} demandes) — "
                + "à croiser avec les opportunités."
            )
        elif g["kind"] == "THEORY":
            proposals.append(
                f"Sondage ou débat : théories sur « {g['subject']} » ({g['count']}) — "
                + "à instruire au laboratoire, jamais présentées comme des faits."
            )
        else:
            proposals.append(
                f"Point contesté sur « {g['subject']} » ({g['count']}) : "
                + "vérifier les sources, corriger publiquement si besoin."
            )
    return {
        "method": METHOD,
        "data_class": "PUBLIC",
        "comments": len(comments),
        "by_kind": dict(by_kind),
        "recurring": recurring,
        "proposals": proposals,
        "rule": "Propositions uniquement : aucune publication ni réponse automatique.",
    }


class YouTubeComments:
    """Fils de commentaires publics d'une vidéo (YouTube Data API v3, 1 unité par page)."""

    def __init__(self, api_key: str, *, transport: httpx.BaseTransport | None = None) -> None:
        if not api_key:
            raise ConnectorError("clé YouTube Data API absente")
        self._key = api_key
        self._client = httpx.Client(base_url=YOUTUBE_API, timeout=20, transport=transport)
        self.units = 0

    def threads(self, video_id: str, *, max_pages: int = 3) -> list[dict[str, Any]]:
        comments: list[dict[str, Any]] = []
        token: str | None = None
        for _ in range(max_pages):
            self.units += 1
            params: dict[str, Any] = {
                "part": "snippet",
                "videoId": video_id,
                "maxResults": 100,
                "textFormat": "plainText",
                "key": self._key,
            }
            if token:
                params["pageToken"] = token
            response = self._client.get("/commentThreads", params=params)
            if response.status_code != 200:
                raise ConnectorError(f"YouTube a refusé la requête (HTTP {response.status_code})")
            data = response.json()
            for item in data.get("items", []):
                top = item["snippet"]["topLevelComment"]["snippet"]
                # Identité de l'auteur volontairement ignorée (nom, chaîne, photo).
                comments.append(
                    {
                        "external_id": item["id"],
                        "text": top.get("textOriginal") or top.get("textDisplay", ""),
                        "like_count": int(top.get("likeCount", 0)),
                        "published_at": top.get("publishedAt"),
                        "language": language_of(None, "fr"),
                    }
                )
            token = data.get("nextPageToken")
            if not token:
                break
        return comments
