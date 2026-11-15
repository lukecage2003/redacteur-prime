import base64
import json
import time
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from starlette.websockets import WebSocketDisconnect

from primestone.config import Settings
from primestone.security import IAP_HEADER, IAP_ISSUER
from primestone_api.main import create_app

# Jetons IAP de test : clé locale générée à la volée.


AUD = "/projects/123/global/backendServices/456"
_KEY = ec.generate_private_key(ec.SECP256R1())
KEYS = {"k1": _KEY.public_key()}


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def good_token() -> str:
    now = time.time()
    head = _b64(json.dumps({"alg": "ES256", "kid": "k1"}).encode())
    body = _b64(json.dumps({"iss": IAP_ISSUER, "aud": AUD, "iat": now, "exp": now + 600}).encode())
    r, s = decode_dss_signature(_KEY.sign(f"{head}.{body}".encode(), ec.ECDSA(hashes.SHA256())))
    return f"{head}.{body}.{_b64(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}"


pytestmark = pytest.mark.integration


def test_iap_guards_http_and_websocket(tmp_path: Path, db_engine: Engine) -> None:
    settings = Settings(
        _env_file=None, environment="test", storage_local_root=tmp_path / "s", iap_audience=AUD
    )
    with TestClient(create_app(settings, engine=db_engine, iap_keys=lambda: KEYS)) as client:
        assert client.get("/api/v1/health").status_code == 200  # sonde exemptée
        assert client.get("/api/v1/scripts").status_code == 401
        assert client.get("/api/v1/scripts", headers={IAP_HEADER: "faux"}).status_code == 401
        assert client.get("/api/v1/scripts", headers={IAP_HEADER: good_token()}).status_code == 200
        with pytest.raises(WebSocketDisconnect), client.websocket_connect("/api/v1/ws/voice") as ws:
            ws.receive_json()
        with client.websocket_connect("/api/v1/ws/voice", headers={IAP_HEADER: good_token()}) as ws:
            ws.send_json({"type": "start", "personality": "director", "language": "fr"})
            assert ws.receive_json()["type"] == "ready"
