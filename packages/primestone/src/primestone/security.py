"""Vérification de l'en-tête signé par Identity-Aware Proxy (défense en profondeur).

En staging/production, l'application n'est joignable que derrière un équilibreur de charge
protégé par IAP ; l'API vérifie EN PLUS chaque requête (et chaque WebSocket) :
signature ES256 avec les clés publiques de Google, émetteur, audience, expiration.
"""

from __future__ import annotations

import base64
import json
import time
from collections.abc import Callable
from typing import Any

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

IAP_ISSUER = "https://cloud.google.com/iap"
IAP_KEYS_URL = "https://www.gstatic.com/iap/verify/public_key-jwk"
IAP_HEADER = "x-goog-iap-jwt-assertion"
LEEWAY_SECONDS = 30

PublicKeys = dict[str, ec.EllipticCurvePublicKey]


class IAPError(PermissionError):
    pass


def _b64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def keys_from_jwks(jwks: dict[str, Any]) -> PublicKeys:
    keys: PublicKeys = {}
    for jwk in jwks.get("keys", []):
        if jwk.get("kty") == "EC" and jwk.get("crv") == "P-256":
            numbers = ec.EllipticCurvePublicNumbers(
                int.from_bytes(_b64(jwk["x"]), "big"),
                int.from_bytes(_b64(jwk["y"]), "big"),
                ec.SECP256R1(),
            )
            keys[jwk["kid"]] = numbers.public_key()
    return keys


class GoogleIAPKeys:
    """Clés publiques d'IAP, mises en cache une heure."""

    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self._client = httpx.Client(timeout=10, transport=transport)
        self._cache: tuple[PublicKeys, float] | None = None

    def __call__(self) -> PublicKeys:
        if self._cache is None or self._cache[1] < time.time():
            response = self._client.get(IAP_KEYS_URL)
            response.raise_for_status()
            self._cache = (keys_from_jwks(response.json()), time.time() + 3600)
        return self._cache[0]


def verify_iap_jwt(
    token: str, *, audience: str, keys: PublicKeys, now: float | None = None
) -> dict[str, Any]:
    """Renvoie les revendications si le jeton est valide, sinon lève IAPError."""
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
        header = json.loads(_b64(header_b64))
        claims: dict[str, Any] = json.loads(_b64(payload_b64))
        signature = _b64(signature_b64)
    except (ValueError, json.JSONDecodeError):
        raise IAPError("jeton IAP illisible") from None
    if header.get("alg") != "ES256":
        raise IAPError("algorithme de signature refusé")
    key = keys.get(str(header.get("kid")))
    if key is None or len(signature) != 64:
        raise IAPError("clé de signature inconnue")
    der = encode_dss_signature(
        int.from_bytes(signature[:32], "big"), int.from_bytes(signature[32:], "big")
    )
    try:
        key.verify(der, f"{header_b64}.{payload_b64}".encode(), ec.ECDSA(hashes.SHA256()))
    except InvalidSignature:
        raise IAPError("signature invalide") from None
    current = time.time() if now is None else now
    if claims.get("iss") != IAP_ISSUER:
        raise IAPError("émetteur inattendu")
    if claims.get("aud") != audience:
        raise IAPError("audience inattendue")
    if float(claims.get("exp", 0)) < current - LEEWAY_SECONDS:
        raise IAPError("jeton expiré")
    if float(claims.get("iat", 0)) > current + LEEWAY_SECONDS:
        raise IAPError("jeton émis dans le futur")
    return claims


class IAPMiddleware:
    """Middleware ASGI : HTTP et WebSocket. Seules les sondes de santé sont exemptées."""

    EXEMPT = ("/api/v1/health",)

    def __init__(
        self, app: Any, *, audience: str, keys: Callable[[], PublicKeys] | None = None
    ) -> None:
        self.app = app
        self.audience = audience
        self.keys = keys or GoogleIAPKeys()

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] not in ("http", "websocket") or str(scope.get("path", "")).startswith(
            self.EXEMPT
        ):
            await self.app(scope, receive, send)
            return
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        try:
            claims = verify_iap_jwt(
                headers.get(IAP_HEADER, ""), audience=self.audience, keys=self.keys()
            )
        except (IAPError, httpx.HTTPError):
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
                return
            body = json.dumps({"detail": "authentification IAP requise"}).encode()
            await send(
                {
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [(b"content-type", b"application/json")],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return
        scope.setdefault("state", {})["user_email"] = claims.get("email")
        await self.app(scope, receive, send)
