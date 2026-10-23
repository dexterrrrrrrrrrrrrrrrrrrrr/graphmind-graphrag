from types import SimpleNamespace

from backend.evaluation.service import metrics


def test_accuracy_does_not_count_reference_in_supporting_quotes_as_answer():
    item = {
        "reference_answer": "Rahul Sharma",
        "supporting_evidence": ["Rahul Sharma founded AlphaTech."],
        "expected_relationships": [],
    }
    response = SimpleNamespace(
        answer="AlphaTech. Supporting facts: Rahul Sharma founded AlphaTech.",
        evidence=[],
        citations=[],
        paths=[],
        strategy="vector",
        latency_ms=1,
        token_usage=None,
        estimated_cost_usd=None,
    )
    assert metrics(item, response, ["doc"])["answer_accuracy"] == 0
    response.answer = "Rahul Sharma. Supporting facts: Rahul Sharma founded AlphaTech."
    assert metrics(item, response, ["doc"])["answer_accuracy"] == 1
