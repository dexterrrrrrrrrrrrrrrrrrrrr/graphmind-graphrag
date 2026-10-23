"""Deterministic model double, imported only by tests. Never application inference."""

from backend.models.schemas import Extraction, ExtractionResponse
from backend.reasoning.answers import AnswerOutput
from backend.reasoning.providers import Completion
from backend.tests.literal_answer import local_answer
from backend.tests.literal_extraction import extract_literal_facts


class FixtureProvider:
    def __init__(self, settings, **kwargs):
        self.settings = settings

    def json(self, system, data, schema, model=None):
        if schema in (Extraction, ExtractionResponse):
            return Completion(
                extract_literal_facts(data["untrusted_document"], self.settings.relationship_types)
            )
        from backend.models.schemas import Evidence

        evidence = [Evidence.model_validate(e) for e in data["evidence"]]
        answer, citations = local_answer(data["question"], evidence, self.settings.max_depth)
        output = AnswerOutput(
            sufficient=bool(citations),
            claims=[]
            if not citations
            else [
                {
                    "text": answer,
                    "citation_ids": [e.chunk_id for e in citations],
                    "quotes": [{"chunk_id": e.chunk_id, "text": e.text} for e in citations],
                }
            ],
        )
        return Completion(output, {"input_tokens": 10, "output_tokens": 10})
