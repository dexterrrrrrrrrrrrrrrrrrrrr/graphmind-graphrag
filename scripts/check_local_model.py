"""Opt-in real Ollama schema/extraction/answer smoke check. Never pulls models."""

import argparse
import json
from pathlib import Path
from time import perf_counter

from backend.core.config import Settings
from backend.knowledge_graph.extraction import extract
from backend.models.schemas import Evidence
from backend.reasoning.answers import generate
from backend.reasoning.providers import Provider

parser = argparse.ArgumentParser()
parser.add_argument("--output", default=".data/local-model-check.json")
args = parser.parse_args()
settings = Settings()
provider = Provider(settings)
status = provider.status()
if not status["ready"]:
    raise SystemExit("Local model check blocked: " + status["message"])
source = "Rahul Sharma founded AlphaTech."
started = perf_counter()
extraction = extract(source, provider, settings)
names = {e.id: e.name for e in extraction.entities}
assert any(
    names[r.source] == "Rahul Sharma"
    and r.type == "FOUNDED"
    and names[r.target] == "AlphaTech"
    and r.evidence in source
    for r in extraction.relationships
), "Model output did not contain the source-supported directed founder relationship"
extraction_ms = (perf_counter() - started) * 1000
started = perf_counter()
answer, citations, usage, warnings = generate(
    "Who founded AlphaTech?",
    [
        Evidence(
            chunk_id="local-smoke-chunk",
            document_id="local-smoke-document",
            document_name="local-smoke.txt",
            text=source,
        )
    ],
    [],
    settings,
    provider,
)
assert "Rahul Sharma" in answer and len(citations) == 1, "Answer/citation check failed"
report = {
    "provider": "ollama",
    "answer_model": settings.llm_model,
    "extraction_model": settings.extraction_model,
    "extraction": extraction.model_dump(),
    "answer": answer,
    "citations": [c.model_dump() for c in citations],
    "extraction_ms": extraction_ms,
    "answer_ms": (perf_counter() - started) * 1000,
    "answer_token_usage": usage,
    "warnings": warnings,
}
output = Path(args.output)
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(report, indent=2))
print("PASS: real Ollama schema-constrained extraction and source-cited answer; report:", output)
