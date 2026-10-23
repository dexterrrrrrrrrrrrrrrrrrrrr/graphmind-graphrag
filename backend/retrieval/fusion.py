import json
import re

from backend.models.schemas import Evidence


def fuse(vector: list[Evidence], graph: list[Evidence], strategy="rrf", weight=0.5):
    merged = {}
    for source, rows, factor in [("vector", vector, weight), ("graph", graph, 1 - weight)]:
        for rank, row in enumerate(rows, 1):
            entry = merged.setdefault(row.chunk_id, row.model_copy(update={"score": 0, "sources": []}))
            contribution = factor / (60 + rank) if strategy == "rrf" else factor * row.score
            entry.score += contribution
            if source not in entry.sources:
                entry.sources.append(source)
    return sorted(merged.values(), key=lambda e: (-e.score, e.chunk_id))


def rerank(question, evidence):
    # Cheap, deterministic lexical rerank blended with the fused rank; no extra model download.
    terms = set(re.findall(r"\w+", question.casefold())) - {
        "the",
        "a",
        "is",
        "which",
        "what",
        "who",
        "to",
        "of",
    }
    original = {e.chunk_id: i for i, e in enumerate(evidence)}

    def score(e):
        overlap = len(terms & set(re.findall(r"\w+", e.text.casefold()))) / max(len(terms), 1)
        return 0.7 / (1 + original[e.chunk_id]) + 0.3 * overlap

    return sorted(evidence, key=score, reverse=True)


def budget(evidence, token_budget):
    # Conservative UTF-8 byte upper bound, including metadata. Never cut a source excerpt mid-quote.
    used, result = 0, []
    for e in evidence:
        estimate = len(json.dumps(e.model_dump(), ensure_ascii=False).encode("utf-8"))
        if used + estimate > token_budget:
            continue
        result.append(e)
        used += estimate
    return result
