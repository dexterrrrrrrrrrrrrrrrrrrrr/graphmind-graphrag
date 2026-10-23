from concurrent.futures import ThreadPoolExecutor
from threading import RLock
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app, rate_windows
from backend.core.config import Settings
from backend.core.store import Store


@pytest.fixture
def client(tmp_path):
    rate_windows.clear()
    settings = Settings(data_dir=tmp_path, requests_per_minute=500)
    context = SimpleNamespace(
        store=Store(tmp_path),
        graph=Mock(),
        graph_ready=True,
        lock=RLock(),
        snapshot=lambda: settings,
        settings=settings,
        executor=ThreadPoolExecutor(max_workers=1),
        ingestor=Mock(),
    )
    app.state.context = context
    yield TestClient(app), context
    context.executor.shutdown()


def test_upload_duplicate_status_delete_and_bad_mime(client):
    api, c = client
    response = api.post(
        "/api/documents/upload", files={"file": ("../../safe.txt", b"A owns B.", "text/plain")}
    )
    assert response.status_code == 202
    id = response.json()["id"]
    assert response.json()["name"] == "safe.txt"
    assert api.get(f"/api/documents/{id}/status").json()["status"] == "queued"
    assert (
        api.post(
            "/api/documents/upload", files={"file": ("safe.txt", b"A owns B.", "text/plain")}
        ).status_code
        == 409
    )
    assert api.delete(f"/api/documents/{id}").status_code == 409
    assert (
        api.post(
            "/api/documents/upload", files={"file": ("fake.pdf", b"A owns B.", "application/pdf")}
        ).status_code
        == 422
    )
    c.store.update_document(id, "ready", 100, 1)
    assert api.delete(f"/api/documents/{id}").status_code == 204
    assert api.get(f"/api/documents/{id}").status_code == 404
    assert not (c.store.directory / "uploads" / id).exists()
    c.graph.delete.assert_called_once_with(id)


def test_settings_never_expose_secrets_and_validate_overlap(client):
    api, c = client
    response = api.get("/api/settings")
    assert response.status_code == 200
    assert "neo4j_password" not in response.text and "api_key" not in response.text
    assert api.patch("/api/settings", json={"chunk_size": 100, "chunk_overlap": 150}).status_code == 422
    assert api.patch("/api/settings", json={"max_depth": 99}).status_code == 422
    assert api.patch("/api/settings", json={"top_k": 3}).status_code == 200
    assert c.store.saved_settings()["top_k"] == 3


def test_query_errors_do_not_fallback(client):
    api, c = client
    c.query = Mock()
    c.query.ask.side_effect = RuntimeError("private internal details")
    response = TestClient(app, raise_server_exceptions=False).post(
        "/api/query", json={"question": "Who owns B?", "mode": "graph"}
    )
    assert response.status_code == 503
    assert "no retrieval fallback" in response.json()["error"]["message"]
    assert "private internal" not in response.text
    assert c.query.ask.call_count == 1


def test_stream_delivers_only_final_validated_answer_or_error(client):
    import json

    api, c = client
    c.query = Mock()
    c.query.ask.return_value.model_dump.return_value = {"answer": "validated fixture"}
    response = api.post("/api/query/stream", json={"question": "Who owns B?"})
    assert response.headers["content-type"].startswith("text/event-stream")
    event = json.loads(response.text.strip().removeprefix("data: "))
    assert event == {"event": "answer", "data": {"answer": "validated fixture"}}
    c.query.ask.side_effect = RuntimeError("private details")
    response = api.post("/api/query/stream", json={"question": "Who owns B?"})
    assert '"event": "error"' in response.text and "private details" not in response.text


def test_nonlocal_provider_selection_is_rejected(client):
    api, _ = client
    assert api.patch("/api/settings", json={"llm_provider": "remote"}).status_code == 422
    assert api.patch("/api/settings", json={"llm_model": "qwen3:cloud"}).status_code == 422
