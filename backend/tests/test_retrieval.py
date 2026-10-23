from unittest.mock import Mock

import pytest

from backend.core.config import Settings
from backend.models.schemas import Evidence, GraphEdge, GraphNode, GraphPath, QueryRequest
from backend.retrieval.fusion import budget, fuse
from backend.retrieval.router import route
from backend.retrieval.service import Retriever


def evidence(id="a", source="vector", score=0.8):
    return Evidence(
        chunk_id=id,
        document_id="doc",
        document_name="source.txt",
        text="AlphaTech acquired DataVision.",
        sources=[source],
        score=score,
    )


@pytest.mark.parametrize(
    "question,strategy",
    [
        ("What is semantic indexing?", "vector"),
        ("Who founded AlphaTech?", "graph"),
        ("Who is indirectly connected through an acquisition?", "hybrid"),
    ],
)
def test_router(question, strategy):
    assert route(question)[0] == strategy


def test_fusion_deduplicates_and_scores():
    a, b = evidence(), evidence("b")
    rows = fuse([a, b], [a.model_copy(update={"sources": ["graph"]})])
    assert len(rows) == 2 and rows[0].chunk_id == "a"
    assert set(rows[0].sources) == {"vector", "graph"}
    assert rows[0].score > rows[1].score
    assert len(budget(rows, 1)) == 0
    assert budget(rows, 10000) == rows
    assert fuse([a], [], strategy="weighted", weight=0.8)[0].score == pytest.approx(0.64)


def test_vector_mode_never_traverses():
    graph, embed = Mock(), Mock()
    graph.vector.return_value = [evidence()]
    r = Retriever(graph, embed).retrieve(QueryRequest(question="Who founded A?", mode="vector"), Settings())
    assert r[0] == "vector" and r[3] == []
    graph.link.assert_not_called()
    graph.traverse.assert_not_called()
    embed.embed_query.assert_called_once()


def test_graph_mode_never_embeds_and_preserves_source_path():
    graph, embed = Mock(), Mock()
    graph.link.return_value = ["a"]
    path = GraphPath(
        nodes=[
            GraphNode(id="a", name="A", type="Organization"),
            GraphNode(id="b", name="B", type="Organization"),
        ],
        edges=[
            GraphEdge(
                id="r",
                source="a",
                target="b",
                type="OWNS",
                evidence="A owns B.",
                chunk_id="a",
                document_id="doc",
                confidence=1,
            )
        ],
    )
    graph.traverse.return_value = [path]
    graph.evidence.return_value = [evidence(source="graph")]
    result = Retriever(graph, embed).retrieve(QueryRequest(question="Who owns B?", mode="graph"), Settings())
    assert len(result[3]) == 1 and result[3][0].edges[0].id == "r"
    embed.embed_query.assert_not_called()
    graph.vector.assert_not_called()
    result = Retriever(graph, embed).retrieve(
        QueryRequest(question="Who owns B?", mode="graph"), Settings(context_tokens=256)
    )
    assert result[3] == []  # Evidence must fit; no unsupported displayed paths.


def test_missing_entity_has_no_fallback():
    graph, embed = Mock(), Mock()
    graph.link.return_value = []
    graph.evidence.return_value = []
    result = Retriever(graph, embed).retrieve(
        QueryRequest(question="Who founded Unknown?", mode="graph"), Settings()
    )
    assert result[2] == [] and result[3] == []
    graph.vector.assert_not_called()
    graph.traverse.assert_not_called()


def test_invalid_traversal_schema():
    from pydantic import ValidationError

    from backend.models.schemas import TraverseRequest

    with pytest.raises(ValidationError):
        TraverseRequest(entity_ids=["a"], max_depth=999)
