from backend.core.store import Store


def test_metadata_query_and_settings_survive_restart(tmp_path):
    s = Store(tmp_path)
    s.create_document("id", "a.txt", "hash", 10, "text/plain")
    s.update_document("id", "ready", 100, 1)
    s.save_settings({"top_k": 3})
    s.record("queries", "query", {"strategy": "graph", "latency_ms": 12})
    fresh = Store(tmp_path)
    assert fresh.document("id")["status"] == "ready"
    assert fresh.duplicate("hash")["id"] == "id"
    assert fresh.saved_settings() == {"top_k": 3}
    assert fresh.query_aggregates()[0]["count"] == 1
    fresh.remove_document("id")
    assert not fresh.documents()


def test_deleted_evidence_is_removed_from_history(tmp_path):
    store = Store(tmp_path)
    store.record("queries", "a", {"evidence": [{"document_id": "deleted", "text": "private"}]})
    store.record("queries", "b", {"evidence": [{"document_id": "retained"}]})
    store.record("evaluations", "c", {"rows": [{"response": {"evidence": [{"document_id": "deleted"}]}}]})
    store.purge_evidence("deleted")
    assert len(store.records("queries")) == 1
    assert store.records("evaluations") == []


def test_ingestion_configuration_is_auditable(tmp_path):
    from backend.core.config import Settings

    store = Store(tmp_path)
    store.create_document("d", "a.txt", "hash", 10, "text/plain")
    store.processing_metadata("d", Settings(neo4j_password="never-store-this"))
    metadata = Store(tmp_path).document("d")["processing_metadata"]
    assert metadata["embedding_model"] == "sentence-transformers/all-MiniLM-L6-v2"
    assert metadata["pipeline_version"] == "graphmind-ollama-v2"
    assert "never-store-this" not in str(metadata)


def test_validated_extraction_cache_survives_restart(tmp_path):
    store = Store(tmp_path)
    assert store.extraction_cache("chunk-model-prompt") is None
    payload = {"entities": [], "relationships": []}
    store.extraction_cache("chunk-model-prompt", payload)
    assert Store(tmp_path).extraction_cache("chunk-model-prompt") == payload
    assert Store(tmp_path).extraction_cache("other-model") is None


def test_deletion_removes_extraction_evidence_without_losing_shared_cache(tmp_path):
    store = Store(tmp_path)
    for id in ("a", "b"):
        store.create_document(id, id + ".txt", id, 10, "text/plain")
    store.extraction_cache("shared", {"evidence": "same"}, document_id="a")
    store.extraction_cache("shared", document_id="b")
    store.extraction_cache("private-a", {"evidence": "deleted"}, document_id="a")
    store.remove_document("a")
    assert store.extraction_cache("private-a") is None
    assert store.extraction_cache("shared") is not None
    store.remove_document("b")
    assert store.extraction_cache("shared") is None
