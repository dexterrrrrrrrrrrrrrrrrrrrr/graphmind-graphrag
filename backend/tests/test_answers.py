from unittest.mock import Mock

from backend.core.config import Settings
from backend.models.schemas import Evidence
from backend.reasoning.answers import INSUFFICIENT, AnswerOutput, generate, verify_claims


def test_citation_ids_and_quotes_must_exist():
    e = Evidence(chunk_id="c1", document_id="d1", document_name="a.txt", text="A owns B.")

    def output(id, quote):
        return AnswerOutput.model_validate(
            {
                "sufficient": True,
                "claims": [
                    {"text": "A owns B.", "citation_ids": [id], "quotes": [{"chunk_id": id, "text": quote}]}
                ],
            }
        )

    assert len(verify_claims(output("c1", "A owns B."), [e])[0]) == 1
    assert verify_claims(output("invented", "A owns B."), [e]) == ([], [])
    assert verify_claims(output("c1", "A owns C."), [e]) == ([], [])


def test_no_evidence_never_calls_llm():
    provider = Mock()
    assert generate("Who?", [], [], Settings(), provider)[0] == INSUFFICIENT
    provider.json.assert_not_called()


def test_model_refusal_is_preserved():
    from backend.reasoning.providers import Completion

    provider = Mock()
    provider.json.return_value = Completion(AnswerOutput(sufficient=False, claims=[]))
    e = Evidence(chunk_id="a", document_id="d", document_name="a.txt", text="AlphaTech acquired DataVision.")
    assert generate("Who founded Unknown?", [e], [], Settings(), provider)[0] == INSUFFICIENT
    provider.json.assert_called_once()


def test_invalid_citation_model_answer_is_rejected():
    from backend.reasoning.providers import Completion

    provider = Mock()
    provider.json.return_value = Completion(
        AnswerOutput(
            sufficient=True,
            claims=[
                {
                    "text": "Invented",
                    "citation_ids": ["missing"],
                    "quotes": [{"chunk_id": "missing", "text": "fabricated"}],
                }
            ],
        )
    )
    e = Evidence(chunk_id="a", document_id="d", document_name="a.txt", text="A owns B.")
    answer, citations, _, warnings = generate("Who owns B?", [e], [], Settings(), provider)
    assert answer == INSUFFICIENT and citations == [] and warnings
