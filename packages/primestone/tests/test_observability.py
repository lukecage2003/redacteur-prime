"""Journalisation JSON structurée et identifiant de requête."""

from __future__ import annotations

import json
import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from primestone.observability import JSONFormatter, RequestIdMiddleware, request_id


def _record(**fields: object) -> logging.LogRecord:
    record = logging.LogRecord(
        "primestone.test", logging.INFO, __file__, 1, "bonjour %s", ("toi",), None
    )
    record.fields = fields
    return record


def test_json_formatter_masks_secrets_and_adds_request_id() -> None:
    token = request_id.set("abc123")
    try:
        line = json.loads(JSONFormatter().format(_record(api_key="sk-x", path="/x")))
    finally:
        request_id.reset(token)
    assert line["message"] == "bonjour toi"
    assert line["severity"] == "INFO"
    assert line["request_id"] == "abc123"
    assert line["api_key"] == "[masqué]"
    assert line["path"] == "/x"


def test_request_id_middleware_propagates_or_generates() -> None:
    app = FastAPI()

    @app.get("/ping")
    def ping() -> dict[str, str | None]:
        return {"rid": request_id.get()}

    app.add_middleware(RequestIdMiddleware)
    client = TestClient(app)
    given = client.get("/ping", headers={"X-Request-ID": "req-42"})
    assert given.headers["x-request-id"] == "req-42"
    assert given.json()["rid"] == "req-42"
    unsafe = client.get("/ping", headers={"X-Request-ID": "bad id\n<script>"})
    assert unsafe.headers["x-request-id"] != "bad id\n<script>"
    assert len(unsafe.headers["x-request-id"]) == 32
