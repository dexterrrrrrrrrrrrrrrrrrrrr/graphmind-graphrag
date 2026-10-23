from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.api.main import app
from backend.core.config import Settings


def test_config_guards():
    with pytest.raises(ValidationError):
        Settings(chunk_size=100, chunk_overlap=100)
    with pytest.raises(ValidationError):
        Settings(max_depth=99)


def test_health_reports_dependency_failure():
    c = Mock(graph_ready=False, embedding_error="Unavailable")
    c.embedder.ready = False
    c.settings = Settings()
    c.snapshot.return_value = c.settings
    app.state.context = c
    response = TestClient(app).get("/api/health")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["embedding_model"] is False


def test_openapi_contains_required_routes():
    schema = TestClient(app).get("/openapi.json").json()
    for endpoint in [
        "/api/query",
        "/api/query/compare",
        "/api/documents/upload",
        "/api/evaluation/run",
        "/api/graph/traverse",
    ]:
        assert endpoint in schema["paths"]
    assert "neo4j_password" not in str(schema)


def test_oversized_request_is_rejected_before_parser():
    response = TestClient(app).post(
        "/api/documents/upload", content=b"x", headers={"content-length": str(100 * 1024 * 1024)}
    )
    assert response.status_code == 413


def test_single_default_model_keeps_independent_configuration():
    defaults = Settings(_env_file=None)
    assert defaults.llm_model == defaults.extraction_model == "qwen3:4b"
    configured = Settings(llm_model="local-answer", extraction_model="local-extractor")
    assert configured.llm_model != configured.extraction_model
