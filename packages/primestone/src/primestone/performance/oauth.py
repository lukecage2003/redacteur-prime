"""Autorisation OAuth de la chaîne du propriétaire (YouTube Analytics, lecture seule, gratuit).

Flux « application installée » avec redirection locale (loopback) : le propriétaire ouvre
l'URL, accepte, et le code revient sur 127.0.0.1. Seul le jeton de rafraîchissement est
conservé, dans `.env` ou Secret Manager — jamais journalisé ni versionné.
"""

from __future__ import annotations

import secrets
import time
from collections.abc import Callable
from urllib.parse import urlencode

import httpx

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 - URL publique, pas un secret
SCOPES = (
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/youtube.readonly",
)


class OAuthError(RuntimeError):
    pass


def consent_url(client_id: str, redirect_uri: str, state: str | None = None) -> tuple[str, str]:
    state = state or secrets.token_urlsafe(16)
    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
    )
    return f"{AUTH_URL}?{query}", state


def exchange_code(
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
    *,
    transport: httpx.BaseTransport | None = None,
) -> str:
    """Code d'autorisation → jeton de rafraîchissement."""
    with httpx.Client(timeout=20, transport=transport) as client:
        response = client.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
    if response.status_code != 200 or "refresh_token" not in response.json():
        raise OAuthError(f"échange refusé (HTTP {response.status_code})")
    return str(response.json()["refresh_token"])


def access_token_provider(
    client_id: str,
    client_secret: str,
    refresh_token: str,
    *,
    transport: httpx.BaseTransport | None = None,
) -> Callable[[], str]:
    """Fournit un jeton d'accès valide (rafraîchi une minute avant expiration)."""
    cache: dict[str, float | str] = {}
    client = httpx.Client(timeout=20, transport=transport)

    def token() -> str:
        if not cache or float(cache["expires"]) - 60 < time.time():
            response = client.post(
                TOKEN_URL,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            if response.status_code != 200:
                raise OAuthError(f"rafraîchissement refusé (HTTP {response.status_code})")
            data = response.json()
            cache.update(
                token=data["access_token"], expires=time.time() + float(data["expires_in"])
            )
        return str(cache["token"])

    return token
