import base64
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from primestone.config import Settings
from primestone.voice import silent_wav
from primestone_api.main import create_app

pytestmark = pytest.mark.integration


@pytest.fixture
def client(tmp_path: Path, db_engine: Engine) -> Iterator[TestClient]:
    settings = Settings(_env_file=None, environment="test", storage_local_root=tmp_path / "s")
    with TestClient(create_app(settings, engine=db_engine)) as c:
        yield c


def test_voice_websocket_text_and_audio(client: TestClient) -> None:
    with client.websocket_connect("/api/v1/ws/voice") as ws:
        ws.send_json({"type": "text", "text": "x"})
        assert "non démarrée" in ws.receive_json()["detail"]
        ws.send_json({"type": "start", "personality": "research", "language": "fr"})
        assert ws.receive_json() == {"type": "ready", "personality": "research"}
        ws.send_json({"type": "text", "text": "Qui est Selina ?"})
        answer = ws.receive_json()
        assert answer["type"] == "answer"
        assert answer["text"].startswith("Je ne trouve rien")  # bibliothèque vide : pas d'invention
        sentence = ws.receive_json()
        assert sentence["type"] == "sentence"
        assert base64.b64decode(sentence["audio"]).startswith(b"RIFF")
        while (event := ws.receive_json())["type"] == "sentence":
            pass
        assert event["type"] == "done"
        ws.send_json({"type": "audio", "wav": base64.b64encode(silent_wav()).decode()})
        assert ws.receive_json() == {"type": "transcript", "text": "Qui est Selina ?"}
        assert ws.receive_json()["type"] == "answer"
        ws.send_json({"type": "interrupt"})
        ws.send_json({"type": "nope"})
        # L'interruption peut arriver avant ou après les premières phrases : on lit jusqu'à
        # obtenir la fin du tour ET l'erreur, sans supposer un nombre fixe d'événements.
        events: list[dict[str, str]] = []
        while not (
            any(e["type"] in ("done", "interrupted") for e in events)
            and any(e.get("detail", "").startswith("type de message inconnu") for e in events)
        ):
            assert len(events) < 50, events
            events.append(ws.receive_json())
