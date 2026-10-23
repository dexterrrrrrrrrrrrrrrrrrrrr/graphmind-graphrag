"""Live Neo4j contract tests use an isolated test database and deterministic test embeddings.
These validate graph/vector plumbing, not semantic quality or any live LLM.
Set TEST_NEO4J_URI to opt in; real embedding acceptance is a separate opt-in test.
"""

import hashlib
import os
from pathlib import Path
from uuid import uuid4

import pytest

from backend.core.config import Settings
from backend.core.store import Store
from backend.ingestion.service import Ingestor
from backend.knowledge_graph.repository import GraphRepository
from backend.models.schemas import QueryRequest
from backend.reasoning.answers import INSUFFICIENT
from backend.reasoning.service import QueryService
from backend.retrieval.service import Retriever

pytestmark = pytest.mark.integration


class FixtureEmbedder:
    model_name = "test-only-sha384-v1"

    def embed(self, texts):
        # Not production embeddings. Isolated test database identifies this model explicitly.
        return [[(b + 1) / 256 for b in hashlib.sha384(t.encode()).digest()] * 8 for t in texts]

    def embed_query(self, text):
        return self.embed([text])[0]


@pytest.fixture
def live_graph(tmp_path, monkeypatch):
    from backend.tests.fixture_provider import FixtureProvider

    monkeypatch.setattr("backend.ingestion.service.Provider", FixtureProvider)
    monkeypatch.setattr("backend.reasoning.service.Provider", FixtureProvider)
    uri = os.getenv("TEST_NEO4J_URI")
    if not uri:
        pytest.skip("Set TEST_NEO4J_URI for isolated live Neo4j integration tests")
    assert uri != os.getenv("NEO4J_URI", "bolt://localhost:7687"), "Tests require a separate Neo4j instance"
    s = Settings(
        neo4j_uri=uri,
        neo4j_password=os.environ["TEST_NEO4J_PASSWORD"],
        data_dir=tmp_path,
        embedding_model=FixtureEmbedder.model_name,
        llm_provider="ollama",
    )
    graph = GraphRepository(s)
    graph.initialize()
    assert graph.stats()["documents"] == 0, (
        "Use an empty dedicated database; stop other fixture servers first"
    )
    store = Store(tmp_path)
    ingestor = Ingestor(store, graph, FixtureEmbedder())
    ids = []
    for file in sorted((Path(__file__).resolve().parents[2] / "datasets/demo").glob("*.txt")):
        id = str(uuid4())
        ids.append(id)
        data = file.read_bytes()
        (tmp_path / "uploads").mkdir(exist_ok=True)
        (tmp_path / "uploads" / id).write_bytes(data)
        store.create_document(id, file.name, hashlib.sha256(data).hexdigest(), len(data), "text/plain")
        ingestor.run(id, s)
        assert store.document(id)["status"] == "ready", store.document(id)
    yield graph, store, s, ids, ingestor
    for id in ids:
        graph.delete(id)
    graph.driver.close()


def test_three_document_path_citations_and_native_vectors(live_graph):
    graph, store, s, ids, _ = live_graph
    query = QueryService(Retriever(graph, FixtureEmbedder()), store)
    q = QueryRequest(
        question="Which organization is indirectly connected to Rahul Sharma through his company's acquisition and subsequent partnership?",
        mode="hybrid",
    )
    response = query.ask(q, s)
    assert "MedCore" in response.answer
    assert {c.document_id for c in response.citations} == set(ids)
    assert any(
        [n.name for n in p.nodes] == ["Rahul Sharma", "AlphaTech", "DataVision", "MedCore"]
        for p in response.paths
    )
    assert any(
        len(p.edges) == 3 and all(e.chunk_id in {c.chunk_id for c in response.citations} for e in p.edges)
        for p in response.paths
    )
    baseline = query.ask(q.model_copy(update={"mode": "vector"}), s)
    assert baseline.paths == [] and baseline.fallback is None
    assert (
        graph.vector(FixtureEmbedder().embed_query("Rahul Sharma founded AlphaTech."), 3, 0)[0].document_id
        == ids[0]
    )
    assert (
        query.ask(QueryRequest(question="Who founded QuantumHarbor?", mode="hybrid"), s).answer
        == INSUFFICIENT
    )


def test_idempotency_delete_and_restart(live_graph):
    graph, store, s, ids, ingestor = live_graph
    before = graph.stats()
    from unittest.mock import patch

    with patch(
        "backend.ingestion.service.extract", side_effect=AssertionError("Unchanged extraction must use cache")
    ):
        ingestor.run(ids[0], s)
    assert store.document(ids[0])["status"] == "ready"
    assert graph.stats() == before
    fresh = GraphRepository(s)
    assert fresh.stats() == before
    assert Store(s.data_dir).document(ids[0])["status"] == "ready"
    fresh.driver.close()
    graph.delete(ids[1])
    assert graph.stats()["chunks"] == before["chunks"] - 1
    assert not graph.read("MATCH ()-[r:FACT]->() WHERE r.document_id=$id RETURN r.id", id=ids[1])
    paths = graph.traverse(graph.link("Rahul Sharma"), 3, 20)
    assert not any(n.name == "MedCore" for p in paths for n in p.nodes)
    assert not graph.read("MATCH (c:Chunk {document_id:$id}) RETURN c.id", id=ids[1])


def test_cycles_and_limits(live_graph):
    graph, store, s, ids, _ = live_graph
    paths = graph.traverse(graph.link("AlphaTech"), 5, 2)
    assert len(paths) <= 10
    assert all(len({n.id for n in p.nodes}) == len(p.nodes) for p in paths)
    assert all(len(p.edges) <= 5 for p in paths)


def test_evaluation_records_actual_outcomes(live_graph):
    from backend.evaluation.service import Evaluator, export_csv, summary

    graph, store, s, ids, _ = live_graph
    service = QueryService(Retriever(graph, FixtureEmbedder()), store)
    evaluator = Evaluator(store, service, Path(__file__).resolve().parents[2] / "datasets/benchmark.json")
    result = evaluator.run(s)
    assert len(result["rows"]) == 8
    assert all(r["status"] == "completed" for r in result["rows"])
    assert len(store.records("evaluations")) == 1
    assert "answer_accuracy" in export_csv(result)
    assert summary([result])["hybrid"]["executed"] == 4
    assert summary([result])["hybrid"]["answer_accuracy"] == 1
    assert all(r["response"]["provider"] == "ollama" for r in result["rows"])


def test_live_sentence_transformer_acceptance(tmp_path):
    if os.getenv("GRAPHMIND_RUN_LIVE_LLM") != "1":
        pytest.skip(
            "GRAPHMIND_RUN_LIVE_LLM=1 requires local Ollama, models and a fresh, separate TEST_NEO4J_URI"
        )
    from backend.embeddings.service import Embedder

    uri = os.environ["TEST_NEO4J_URI"]
    assert uri != os.getenv("NEO4J_URI", "bolt://localhost:7687")
    settings = Settings(
        neo4j_uri=uri,
        neo4j_password=os.environ["TEST_NEO4J_PASSWORD"],
        data_dir=tmp_path,
        llm_provider="ollama",
    )
    from backend.reasoning.providers import Provider

    assert Provider(settings).status()["ready"], "Local Ollama/models unavailable; live acceptance cannot run"
    graph = GraphRepository(settings)
    graph.initialize()
    assert graph.stats()["documents"] == 0, "Use a fresh dedicated semantic-test database"
    embedder = Embedder(settings.embedding_model, settings.embedding_dimension)
    store = Store(tmp_path)
    ingestor = Ingestor(store, graph, embedder)
    ids = []
    try:
        for file in sorted((Path(__file__).resolve().parents[2] / "datasets/demo").glob("*.txt")):
            id = str(uuid4())
            ids.append(id)
            data = file.read_bytes()
            (tmp_path / "uploads").mkdir(exist_ok=True)
            (tmp_path / "uploads" / id).write_bytes(data)
            store.create_document(id, file.name, hashlib.sha256(data).hexdigest(), len(data), "text/plain")
            ingestor.run(id, settings)
            assert store.document(id)["status"] == "ready", store.document(id)
        service = QueryService(Retriever(graph, embedder), store)
        request = QueryRequest(
            question="Which organization is indirectly connected to Rahul Sharma through his company's acquisition and subsequent partnership?",
            mode="hybrid",
        )
        response = service.ask(request, settings)
        assert "MedCore" in response.answer
        assert {c.document_id for c in response.citations} == set(ids)
        assert any(
            [n.name for n in p.nodes] == ["Rahul Sharma", "AlphaTech", "DataVision", "MedCore"]
            for p in response.paths
        )
        baseline = service.ask(request.model_copy(update={"mode": "vector"}), settings)
        assert baseline.paths == []
        fresh = GraphRepository(settings)
        assert fresh.stats()["documents"] == 3
        fresh.driver.close()
    finally:
        for id in ids:
            graph.delete(id)
        graph.driver.close()


@pytest.mark.parametrize("depth", [1, 2, 3])
def test_hop_bounds_direction_and_provenance(live_graph, depth):
    graph, _, _, ids, _ = live_graph
    paths = graph.traverse(graph.link("Rahul Sharma"), depth, 20)
    longest = max(paths, key=lambda p: len(p.edges))
    assert len(longest.edges) == depth
    assert [n.name for n in longest.nodes] == ["Rahul Sharma", "AlphaTech", "DataVision", "MedCore"][
        : depth + 1
    ]
    for i, edge in enumerate(longest.edges):
        assert (edge.source, edge.target) == (longest.nodes[i].id, longest.nodes[i + 1].id)
        evidence = graph.evidence([edge.chunk_id])
        assert len(evidence) == 1
        assert evidence[0].document_id == edge.document_id == ids[i]
        assert edge.evidence in evidence[0].text
    reverse = graph.traverse(graph.link("MedCore"), depth, 20)
    # Retrieval can follow incoming edges; semantic direction must never be reversed.
    for path in reverse:
        for i, edge in enumerate(path.edges):
            assert (edge.source, edge.target) == (path.nodes[i + 1].id, path.nodes[i].id)
    assert graph.traverse(graph.link("Rahul Sharma"), depth, 20, allowed=["OWNS"]) == []
    filtered = graph.traverse(graph.link("Rahul Sharma"), depth, 20, document_id=ids[0])
    assert filtered and all(len(p.edges) == 1 and p.edges[0].document_id == ids[0] for p in filtered)


def test_actual_cycle_never_repeats_nodes_or_exceeds_depth(live_graph):
    graph, store, settings, ids, ingestor = live_graph
    id = str(uuid4())
    ids.append(id)  # The fixture owns cleanup of this additional source document.
    data = b"MedCore owns AlphaTech."
    (store.directory / "uploads" / id).write_bytes(data)
    store.create_document(id, "cycle.txt", hashlib.sha256(data).hexdigest(), len(data), "text/plain")
    ingestor.run(id, settings)
    assert store.document(id)["status"] == "ready"
    assert graph.stats()["relationships"] == 4
    paths = graph.traverse(graph.link("Rahul Sharma"), 5, 20)
    assert paths and all(len({n.id for n in p.nodes}) == len(p.nodes) for p in paths)
    assert all(len(p.edges) <= 3 for p in paths)  # Four nodes; no cyclic revisit is allowed.
    keys = [tuple(e.id for e in p.edges) for p in paths]
    assert len(keys) == len(set(keys))


def test_partially_invalid_ollama_response_persists_valid_partnership(live_graph, monkeypatch):
    from backend.tests.test_partial_extraction import ENTITIES, VALID, provider_for

    graph, store, settings, ids, ingestor = live_graph
    before = graph.stats()
    provider = provider_for(
        {
            "entities": ENTITIES,
            "relationships": [{**VALID, "target": "e1"}, {**VALID, "target": "unknown"}, VALID],
        }
    )
    monkeypatch.setattr("backend.ingestion.service.Provider", lambda settings: provider)
    # Force inference for this test only with a different context cache key.
    ingestor.run(ids[2], settings.model_copy(update={"ollama_context_length": 8192}))
    document = store.document(ids[2])
    assert document["status"] == "ready"
    assert document["processing_metadata"]["extraction_diagnostics"]["rejected_relationship_count"] == 2
    assert graph.stats() == before
    paths = graph.traverse(graph.link("Rahul Sharma"), 3, 20)
    assert any(
        [n.name for n in p.nodes] == ["Rahul Sharma", "AlphaTech", "DataVision", "MedCore"] for p in paths
    )
    assert not graph.read("MATCH (e:Entity)-[r:FACT]->(e) RETURN r.id")
