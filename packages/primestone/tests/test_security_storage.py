import base64
import json
import time
from pathlib import Path

import httpx
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from pydantic import ValidationError

from primestone.config import Settings
from primestone.security import IAP_ISSUER, IAPError, keys_from_jwks, verify_iap_jwt
from primestone.storage import GCSObjectStore, ObjectNotFoundError, create_object_store

AUD = "/projects/123/global/backendServices/456"
KEY = ec.generate_private_key(ec.SECP256R1())


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def make_token(claims: dict, *, kid: str = "k1", key: ec.EllipticCurvePrivateKey = KEY) -> str:
    head = b64(json.dumps({"alg": "ES256", "kid": kid}).encode())
    body = b64(json.dumps(claims).encode())
    r, s = decode_dss_signature(key.sign(f"{head}.{body}".encode(), ec.ECDSA(hashes.SHA256())))
    return f"{head}.{body}.{b64(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}"


def good_claims(**over: object) -> dict:
    now = time.time()
    return {"iss": IAP_ISSUER, "aud": AUD, "iat": now, "exp": now + 600, "email": "moi@x", **over}


KEYS = {"k1": KEY.public_key()}


def test_valid_iap_token() -> None:
    assert verify_iap_jwt(make_token(good_claims()), audience=AUD, keys=KEYS)["email"] == "moi@x"


@pytest.mark.parametrize(
    ("token", "message"),
    [
        (lambda: make_token(good_claims(aud="autre")), "audience"),
        (lambda: make_token(good_claims(iss="https://evil")), "émetteur"),
        (lambda: make_token(good_claims(exp=time.time() - 3600)), "expiré"),
        (lambda: make_token(good_claims(), kid="inconnu"), "clé"),
        (
            lambda: make_token(good_claims(), key=ec.generate_private_key(ec.SECP256R1())),
            "signature",
        ),
        (lambda: "pas.un.jeton", "illisible"),
        (lambda: "", "illisible"),
    ],
)
def test_invalid_iap_tokens(token, message: str) -> None:
    with pytest.raises(IAPError, match=message):
        verify_iap_jwt(token(), audience=AUD, keys=KEYS)


def test_keys_from_jwks() -> None:
    numbers = KEY.public_key().public_numbers()
    jwks = {
        "keys": [
            {
                "kty": "EC",
                "crv": "P-256",
                "kid": "k1",
                "x": b64(numbers.x.to_bytes(32, "big")),
                "y": b64(numbers.y.to_bytes(32, "big")),
            }
        ]
    }
    keys = keys_from_jwks(jwks)
    assert verify_iap_jwt(make_token(good_claims()), audience=AUD, keys=keys)["aud"] == AUD


def test_cloud_settings_require_iap_and_bucket() -> None:
    base = {
        "_env_file": None,
        "environment": "production",
        "database_url": "postgresql+psycopg://u@db/p",
        "ai_provider": "ollama",
        "vision_provider": "ollama",
        "storage_backend": "gcs",
        "gcs_bucket": "primestone-prod",
    }
    with pytest.raises(ValidationError, match="IAP_AUDIENCE"):
        Settings(**base)
    assert Settings(**base, iap_audience=AUD).iap_audience == AUD
    with pytest.raises(ValidationError, match="GCS_BUCKET"):
        Settings(_env_file=None, storage_backend="gcs")


def test_gcs_store(tmp_path: Path) -> None:
    objects: dict[str, bytes] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer T"
        path = request.url.path
        if request.method == "POST" and path.startswith("/upload/"):
            objects[request.url.params["name"]] = request.read()
            return httpx.Response(200, json={})
        key = path.split("/o/", 1)[1].replace("%2F", "/")
        if key not in objects:
            return httpx.Response(404)
        if request.url.params.get("alt") == "media":
            return httpx.Response(200, content=objects[key])
        return httpx.Response(200, json={"size": str(len(objects[key]))})

    store = GCSObjectStore(
        "primestone-test", transport=httpx.MockTransport(handler), token=lambda: "T"
    )
    store.put_bytes("pages/ab/x.webp", b"image", "image/webp")
    src = tmp_path / "f.pdf"
    src.write_bytes(b"%PDF-1")
    store.put_file("originals/ab/f.pdf", src, "application/pdf")
    assert store.exists("pages/ab/x.webp")
    assert store.size("originals/ab/f.pdf") == 6
    assert store.open("pages/ab/x.webp").read() == b"image"
    with store.local_copy("originals/ab/f.pdf") as path:
        assert path.read_bytes() == b"%PDF-1"
    assert not store.exists("absent/x")
    with pytest.raises(ObjectNotFoundError):
        store.open("absent/x")
    with pytest.raises(ValueError, match="clé"):
        store.put_bytes("../evil", b"", "x")
    with pytest.raises(ValueError, match="bucket"):
        GCSObjectStore("Bad_Bucket!")
    with pytest.raises(ValueError, match="GCS_BUCKET"):
        create_object_store("gcs", tmp_path)
