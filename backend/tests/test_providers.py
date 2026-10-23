import json

import httpx
import pytest

from backend.core.config import Settings
from backend.models.schemas import Extraction
from backend.reasoning.providers import Provider, ProviderError


def transport_for(raw='{"entities": [], "relationships": []}', installed=True, done=True):
    def handler(request):
        if request.url.path == "/api/tags":
            return httpx.Response(
                200, json={"models": [{"name": "test-model", "size": 100}] if installed else []}
            )
        if request.url.path == "/api/ps":
            return httpx.Response(200, json={"models": []})
        body = json.loads(request.content)
        assert request.url.host == "localhost"
        assert body["stream"] is True and body["think"] is False
        assert body["options"]["num_ctx"] == 16384
        assert body["keep_alive"] == 0 and body["format"]["type"] == "object"
        payload = {"message": {"content": raw}, "done": done, "prompt_eval_count": 10, "eval_count": 4}
        return httpx.Response(200, text=json.dumps(payload) + "\n")

    return httpx.MockTransport(handler)


def test_ollama_streamed_json_and_measured_usage():
    events = []
    result = Provider(Settings(llm_model="test-model"), transport_for(), lambda *e: events.append(e)).json(
        "untrusted", {}, Extraction
    )
    assert result.value.entities == []
    assert result.usage == {"input_tokens": 10, "output_tokens": 4}
    assert [e[0] for e in events] == ["loading", "generating"]


def test_missing_model_never_downloads_or_falls_back():
    with pytest.raises(ProviderError, match="not installed"):
        Provider(Settings(llm_model="test-model"), transport_for(installed=False)).json(
            "JSON", {}, Extraction
        )


def test_malformed_output_is_not_repaired_into_facts():
    with pytest.raises(ValueError):
        Provider(Settings(llm_model="test-model"), transport_for("not json")).json("JSON", {}, Extraction)


def test_interrupted_stream_is_rejected():
    with pytest.raises(ProviderError, match="before completion"):
        Provider(Settings(llm_model="test-model"), transport_for(done=False)).json("JSON", {}, Extraction)


def test_health_distinguishes_connection_and_model_availability():
    p = Provider(Settings(llm_model="test-model", extraction_model="test-model"), transport_for())
    assert p.status()["ready"]
    missing = Provider(Settings(), transport_for()).status()
    assert missing["connected"] and not missing["ready"] and missing["missing_models"] == ["qwen3:4b"]


def test_cloud_models_and_endpoints_are_rejected():
    for kwargs in [{"ollama_base_url": "https://ollama.com"}, {"llm_model": "qwen3:cloud"}]:
        with pytest.raises(ValueError):
            Settings(**kwargs)
    transport = httpx.MockTransport(
        lambda r: httpx.Response(
            200,
            json={
                "models": [
                    {"name": "cloud-model", "remote_host": "ollama.com"},
                    {"name": "local-model"},
                ]
            },
        )
    )
    assert [m["name"] for m in Provider(Settings(), transport).models()] == ["local-model"]


def test_unavailable_ollama_has_actionable_status():
    def handler(request):
        raise httpx.ConnectError("not running")

    status = Provider(Settings(), httpx.MockTransport(handler)).status()
    assert not status["connected"] and not status["ready"]
    assert "Start Ollama" in status["message"]


def test_transient_ollama_error_is_retried(monkeypatch):
    from tenacity import wait_none

    monkeypatch.setattr(Provider.json.retry, "wait", wait_none())
    calls = []
    underlying = transport_for().handler

    def handler(request):
        calls.append(request.url.path)
        if len(calls) == 1:
            return httpx.Response(503)
        return underlying(request)

    result = Provider(Settings(llm_model="test-model"), httpx.MockTransport(handler)).json(
        "JSON", {}, Extraction
    )
    assert result.value.entities == [] and calls.count("/api/tags") == 2
