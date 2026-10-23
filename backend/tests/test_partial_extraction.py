"""Recorded failure-shape regressions. Ollama HTTP is mocked, not real Qwen inference."""

import hashlib
import json
from unittest.mock import Mock

import httpx
import pytest
from pydantic import ValidationError

from backend.core.config import Settings
from backend.core.store import Store
from backend.ingestion.service import Ingestor
from backend.knowledge_graph.extraction import extract, retain_valid_relationships
from backend.models.schemas import Extraction, ExtractionResponse, RelationshipInput
from backend.reasoning.providers import Provider

TEXT = "DataVision partnered with MedCore."
ENTITIES = [
    {"id": "e1", "name": "DataVision", "type": "Organization"},
    {"id": "e2", "name": "MedCore", "type": "Organization"},
]
VALID = {"source": "e1", "target": "e2", "type": "PARTNERED_WITH", "evidence": TEXT, "confidence": 0.9}


def payload(relationships):
    return ExtractionResponse(entities=ENTITIES, relationships=relationships)


def provider_for(value):
    def handler(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen3:4b"}]})
        assert request.url.path == "/api/chat"
        body = json.loads(request.content)
        schema = body["format"]
        assert schema["properties"]["relationships"]["items"]["required"] == [
            "source",
            "target",
            "type",
            "evidence",
        ]
        assert "MUST be different ids" in body["messages"][0]["content"]
        assert body["model"] == "qwen3:4b" and body["think"] is False
        return httpx.Response(
            200,
            text=json.dumps(
                {
                    "message": {"content": json.dumps(value)},
                    "done": True,
                }
            )
            + "\n",
        )

    return Provider(Settings(), httpx.MockTransport(handler))


@pytest.mark.parametrize(
    "bad,reason",
    [
        ({**VALID, "target": "e1"}, "self_reference"),
        ({**VALID, "target": "missing"}, "unknown_entity_reference"),
        ({**VALID, "source": "DataVision"}, "unknown_entity_reference"),
        ({**VALID, "evidence": "DataVision acquired MedCore."}, "invalid_evidence"),
        ({**VALID, "type": "INVENTED"}, "unsupported_relationship_type"),
        ({**VALID, "evidence": "DataVision"}, "missing_endpoint_in_evidence"),
        ({**VALID, "confidence": 2}, "invalid_relationship_schema"),
        ({"source": "e1"}, "invalid_relationship_schema"),
        (None, "invalid_relationship_schema"),
    ],
)
def test_individual_invalid_relationship_is_discarded_without_losing_valid_facts(bad, reason):
    provider = provider_for({"entities": ENTITIES, "relationships": [bad, VALID]})
    value = extract(TEXT, provider, Settings())
    assert [e.name for e in value.entities] == ["DataVision", "MedCore"]
    assert value.relationships == [RelationshipInput(**VALID)]
    assert len(value.rejected_relationships) == 1
    assert value.rejected_relationships[0].index == 0
    assert reason in value.rejected_relationships[0].reason
    # The retained object still satisfies the strict graph schema.
    assert Extraction.model_validate(value.model_dump()).relationships == value.relationships


@pytest.mark.parametrize("relationships", [[], [VALID]])
def test_empty_and_valid_partnership_extraction(relationships):
    value = extract(TEXT, provider_for({"entities": ENTITIES, "relationships": relationships}), Settings())
    assert len(value.entities) == 2
    assert len(value.relationships) == len(relationships)
    assert not value.rejected_relationships
    if relationships:
        assert value.relationships[0].source == "e1" and value.relationships[0].target == "e2"
        assert value.relationships[0].evidence == TEXT


def test_only_invalid_relationship_retains_entities_without_inventing_replacement():
    value = retain_valid_relationships(payload([{**VALID, "target": "e1"}]), TEXT, ["PARTNERED_WITH"])
    assert len(value.entities) == 2 and value.relationships == []
    assert value.rejected_relationships[0].reason == "self_reference"


def test_canonical_self_edge_is_discarded_after_type_normalization():
    value = retain_valid_relationships(
        ExtractionResponse(
            entities=[
                {"id": "e1", "name": "MedCore", "type": "Company"},
                {"id": "e2", "name": "MEDCORE", "type": "Organization"},
            ],
            relationships=[{**VALID, "evidence": "MedCore partnered with MEDCORE."}],
        ),
        "MedCore partnered with MEDCORE.",
        ["PARTNERED_WITH"],
    )
    assert len(value.entities) == 2 and not value.relationships
    assert value.rejected_relationships[0].reason == "canonical_self_reference"


def test_duplicate_entity_ids_remain_fatal_instead_of_guessing_identity():
    value = payload([VALID])
    value.entities[1].id = "e1"
    with pytest.raises(ValidationError, match="Duplicate extraction entity IDs"):
        retain_valid_relationships(value, TEXT, ["PARTNERED_WITH"])


@pytest.mark.parametrize("include_valid", [True, False])
def test_ingestion_with_partially_invalid_output_and_cached_diagnostics(tmp_path, monkeypatch, include_valid):
    store, graph = Store(tmp_path), Mock()
    graph.read.return_value = []
    (tmp_path / "uploads").mkdir()
    (tmp_path / "uploads" / "document").write_text(TEXT)
    store.create_document(
        "document", "03-partnership.txt", hashlib.sha256(TEXT.encode()).hexdigest(), len(TEXT), "text/plain"
    )
    candidates = [{**VALID, "target": "e1"}] + ([VALID] if include_valid else [])
    wire = {"entities": ENTITIES, "relationships": candidates}
    provider = provider_for(wire)
    monkeypatch.setattr("backend.ingestion.service.Provider", lambda settings: provider)
    embedder = Mock(model_name="test-model")
    embedder.embed.return_value = [[0.1] * 384]
    ingestor = Ingestor(store, graph, embedder)
    settings = Settings(data_dir=tmp_path)
    ingestor.run("document", settings)
    document = store.document("document")
    assert document["status"] == "ready" and document["progress"] == 100
    diagnostics = document["processing_metadata"]["extraction_diagnostics"]
    assert diagnostics["rejected_relationship_count"] == 1
    assert diagnostics["details"][0]["reason"] == "self_reference"
    stored = graph.persist.call_args.args[2][0]
    assert len(stored.entities) == 2 and len(stored.relationships) == int(include_valid)
    assert diagnostics["details"][0]["chunk_id"] == graph.persist.call_args.args[1][0]["id"]
    graph.delete.assert_not_called()
    monkeypatch.setattr("backend.ingestion.service.extract", Mock(side_effect=AssertionError("Use cache")))
    ingestor.run("document", settings)
    assert store.document("document")["status"] == "ready"
    assert store.document("document")["processing_metadata"]["extraction_diagnostics"] == diagnostics
