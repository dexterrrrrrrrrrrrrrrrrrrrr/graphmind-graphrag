import csv
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from backend.models.schemas import QueryRequest
from backend.reasoning.answers import INSUFFICIENT


def normalize(text):
    return " ".join(re.findall(r"\w+", text.casefold()))


def metrics(item, response, document_ids):
    expected_docs = set(document_ids)
    reference = item["reference_answer"]
    # Strict normalized containment is a transparent proxy, not a semantic judge.
    answer_accuracy = (
        (normalize(reference) in normalize(response.answer.split("Supporting facts:")[0]))
        if reference
        else response.answer == INSUFFICIENT
    )
    expected_evidence = item["supporting_evidence"]
    correct_citations = [e for e in response.citations if any(s in e.text for s in expected_evidence)]
    expected_edges = {tuple(e) for e in item["expected_relationships"]}
    path_correct = not expected_edges
    for path in response.paths:
        names = {n.id: n.name for n in path.nodes}
        actual = {(names[e.source], e.type, names[e.target]) for e in path.edges}
        if expected_edges <= actual:
            path_correct = True
    return {
        "answer_accuracy": float(answer_accuracy),
        "evidence_recall": (
            sum(
                any(s in e.text and e.document_id in expected_docs for e in response.evidence)
                for s in expected_evidence
            )
            / len(expected_evidence)
        )
        if expected_evidence
        else None,
        "citation_correctness": len(correct_citations) / len(response.citations)
        if response.citations
        else None,
        "graph_path_correctness": float(path_correct)
        if expected_edges and response.strategy != "vector"
        else None,
        "latency_ms": response.latency_ms,
        "token_usage": response.token_usage,
        "estimated_cost_usd": response.estimated_cost_usd,
    }


class Evaluator:
    def __init__(self, store, query, dataset_path: Path):
        self.store, self.query, self.dataset_path = store, query, dataset_path

    def run(self, settings):
        dataset = json.loads(self.dataset_path.read_text())
        ready = [d for d in self.store.documents() if d["status"] == "ready"]
        documents = {d["name"]: d["id"] for d in ready}
        required = {name for q in dataset["questions"] for name in q["supporting_documents"]}
        if not required <= documents.keys():
            raise ValueError("Upload and finish processing all datasets/demo documents before evaluating")
        if any(sum(d["name"] == name for d in ready) != 1 for name in required):
            raise ValueError(
                "Ambiguous benchmark filenames; keep exactly one ready copy of each demo document"
            )
        result = {
            "id": str(uuid4()),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "dataset_version": dataset["version"],
            "provider": settings.llm_provider,
            "model": settings.llm_model,
            "settings": {
                k: getattr(settings, k)
                for k in [
                    "top_k",
                    "max_depth",
                    "similarity_threshold",
                    "context_tokens",
                    "fusion",
                    "vector_weight",
                    "reranking",
                    "embedding_model",
                    "extraction_model",
                    "ollama_context_length",
                    "max_output_tokens",
                    "request_timeout",
                ]
            },
            "rows": [],
        }
        # One immutable settings snapshot, no fallbacks. Failed calls are recorded as failures.
        for item in dataset["questions"]:
            for mode in ("vector", "hybrid"):
                row = {
                    "question_id": item["id"],
                    "question": item["question"],
                    "mode": mode,
                    "required_hops": item["required_hops"],
                    "question_type": item["question_type"],
                }
                try:
                    response = self.query.ask(
                        QueryRequest(question=item["question"], mode=mode, max_depth=item.get("max_depth")),
                        settings,
                        record=False,
                    )
                    row.update(
                        status="completed",
                        response=response.model_dump(),
                        metrics=metrics(item, response, [documents[n] for n in item["supporting_documents"]]),
                    )
                except Exception as error:
                    row.update(status="failed", error=type(error).__name__, metrics=None)
                result["rows"].append(row)
        self.store.record("evaluations", result["id"], result)
        return result


def summary(results):
    rows = [r for result in results for r in result["rows"]]
    output = {}
    for mode in ("vector", "hybrid"):
        selected = [r for r in rows if r["mode"] == mode]
        ok = [r for r in selected if r["metrics"] is not None]
        measures = {}
        for metric in (
            "answer_accuracy",
            "evidence_recall",
            "citation_correctness",
            "graph_path_correctness",
            "latency_ms",
        ):
            values = [r["metrics"][metric] for r in ok if r["metrics"][metric] is not None]
            measures[metric] = sum(values) / len(values) if values else None
        multi = [r["metrics"]["answer_accuracy"] for r in ok if r["required_hops"] >= 2]
        output[mode] = {
            **measures,
            "multi_hop_accuracy": sum(multi) / len(multi) if multi else None,
            "executed": len(ok),
            "failed": len(selected) - len(ok),
        }
    return output


def export_csv(result):
    stream = io.StringIO()
    writer = csv.DictWriter(
        stream,
        fieldnames=[
            "question_id",
            "mode",
            "status",
            "required_hops",
            "answer_accuracy",
            "evidence_recall",
            "citation_correctness",
            "graph_path_correctness",
            "latency_ms",
            "token_usage",
            "estimated_cost_usd",
        ],
    )
    writer.writeheader()
    for row in result["rows"]:
        writer.writerow(
            {
                **{k: row[k] for k in ["question_id", "mode", "status", "required_hops"]},
                **(row["metrics"] or {}),
            }
        )
    return stream.getvalue()
