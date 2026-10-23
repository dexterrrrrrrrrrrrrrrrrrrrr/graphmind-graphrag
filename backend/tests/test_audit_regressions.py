"""Deterministic cloud regressions; no live Ollama inference or production data."""

from threading import Lock
from unittest.mock import Mock

import pytest

from backend.core.config import Settings
from backend.core.context import Context
from backend.core.store import Store
from backend.evaluation.service import metrics
from backend.ingestion.service import Ingestor
from backend.knowledge_graph.extraction import validate_extraction
from backend.models.schemas import Evidence, Extraction
from backend.reasoning.answers import AnswerOutput, verify_claims


def test_every_quote_must_be_exact_even_with_a_valid_quote_for_same_chunk():
    evidence = Evidence(chunk_id="c", document_id="d", document_name="a.txt", text="A owns B.")
    output = AnswerOutput(
        sufficient=True,
        claims=[
            {
                "text": "A owns B.",
                "citation_ids": ["c"],
                "quotes": [{"chunk_id": "c", "text": "A owns B."}, {"chunk_id": "c", "text": "Fabricated"}],
            }
        ],
    )
    assert verify_claims(output, [evidence]) == ([], [])
    output.claims[0].quotes.pop()
    output.claims[0].text = "   "
    assert verify_claims(output, [evidence]) == ([], [])


def test_benchmark_rejects_citation_from_wrong_document():
    from types import SimpleNamespace

    citation = Evidence(chunk_id="c", document_id="wrong", document_name="a.txt", text="A owns B.")
    response = SimpleNamespace(
        answer="A",
        evidence=[citation],
        citations=[citation],
        paths=[],
        strategy="vector",
        latency_ms=1,
        token_usage=None,
        estimated_cost_usd=None,
    )
    item = {"reference_answer": "A", "supporting_evidence": ["A owns B."], "expected_relationships": []}
    result = metrics(item, response, ["correct"])
    assert result["citation_correctness"] == 0 and result["evidence_recall"] == 0


@pytest.mark.parametrize(
    "entity",
    [
        {"id": "a", "name": " ", "type": "Person"},
        {"id": "a", "name": "A", "type": " "},
        {"id": "a", "name": "A", "type": "Person", "aliases": [" "]},
        {"id": "a", "name": "Alpha", "type": "Organization"},
    ],
)
def test_extraction_rejects_blank_or_partial_name(entity):
    with pytest.raises(ValueError):
        validate_extraction(Extraction(entities=[entity]), "AlphaTech owns B.", ["OWNS"])


def test_extraction_rejects_self_relationship_after_normalization():
    extraction = Extraction(
        entities=[
            {"id": "a", "name": "AlphaTech", "type": "Company"},
            {"id": "b", "name": "ALPHATECH", "type": "Organization"},
        ],
        relationships=[
            {"source": "a", "target": "b", "type": "OWNS", "evidence": "AlphaTech owns ALPHATECH."}
        ],
    )
    with pytest.raises(ValueError, match="same entity"):
        validate_extraction(extraction, "AlphaTech owns ALPHATECH.", ["OWNS"])


def test_ingestion_connection_failure_records_failed_job_without_deleting_unknown_graph(tmp_path):
    store, graph = Store(tmp_path), Mock()
    store.create_document("d", "a.txt", "digest", 10, "text/plain")
    graph.read.side_effect = RuntimeError("connection unavailable")
    Ingestor(store, graph, Mock()).run("d", Settings(data_dir=tmp_path))
    assert store.document("d")["status"] == "failed"
    graph.delete.assert_not_called()


def test_failed_startup_recovers_after_cooldown_without_restarting_jobs(monkeypatch):
    context = Context.__new__(Context)
    context.graph, context.store = Mock(), Mock()
    context.graph_ready, context.startup_error = False, None
    context._graph_lock, context._graph_retry_at = Lock(), 0
    clock = [100.0]
    monkeypatch.setattr("backend.core.context.monotonic", lambda: clock[0])
    context.graph.initialize.side_effect = [RuntimeError("starting"), None]
    context.ensure_graph()
    assert not context.graph_ready
    context.ensure_graph()
    assert context.graph.initialize.call_count == 1
    clock[0] += 16
    context.ensure_graph()
    assert context.graph_ready and context.startup_error is None
    context.store.update_document.assert_not_called()


def test_settings_snapshot_does_not_wait_for_long_running_inference():
    from concurrent.futures import ThreadPoolExecutor
    from threading import RLock

    context = Context.__new__(Context)
    context.settings, context.lock = Settings(), RLock()
    with ThreadPoolExecutor(max_workers=1) as executor:
        with context.lock:
            snapshot = executor.submit(context.snapshot).result(timeout=1)
    assert snapshot == context.settings and snapshot is not context.settings
