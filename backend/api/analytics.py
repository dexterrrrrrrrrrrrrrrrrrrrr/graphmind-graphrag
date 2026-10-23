from fastapi import APIRouter, Request

from backend.api.dependencies import ctx, require_graph
from backend.evaluation.service import summary
from backend.models.schemas import OverviewResponse

router = APIRouter()


@router.get("/api/analytics/overview", response_model=OverviewResponse)
def overview(request: Request) -> dict:
    c = ctx(request)
    require_graph(c)
    records = c.store.records("queries", 1000)
    aggregate = c.store.query_aggregates()
    docs = c.store.documents()
    return {
        **c.graph.stats(),
        "documents": len(docs),
        "queries": sum(r["count"] for r in aggregate),
        "recent_queries": records[:6],
        "ingestion": {
            status: sum(d["status"] == status for d in docs)
            for status in ["ready", "failed", "queued", "extracting", "embedding", "indexing", "parsing"]
        },
        "recent_documents": docs[:6],
        "retrieval": aggregate,
        "metrics_window": min(len(records), 1000),
    }


@router.get("/api/analytics/latency")
def latency(request: Request) -> dict:
    import numpy as np

    records = ctx(request).store.records("queries", 1000)
    values = [r["latency_ms"] for r in records]
    return {
        "window": len(values),
        "average_ms": float(np.mean(values)) if values else None,
        "p50_ms": float(np.percentile(values, 50)) if values else None,
        "p95_ms": float(np.percentile(values, 95)) if values else None,
        "samples": [
            {"id": r["id"], "strategy": r["strategy"], "latency_ms": r["latency_ms"]} for r in records[:100]
        ],
        "token_usage": {
            "input_tokens": sum(r["token_usage"]["input_tokens"] for r in records if r["token_usage"]),
            "output_tokens": sum(r["token_usage"]["output_tokens"] for r in records if r["token_usage"]),
        },
        "usage_measured_queries": sum(r["token_usage"] is not None for r in records),
    }


@router.get("/api/analytics/retrieval")
def retrieval_analytics(request: Request) -> dict:
    c = ctx(request)
    records = c.store.records("queries", 1000)
    return {
        "distribution": c.store.query_aggregates(),
        "window": len(records),
        "average_evidence_count": sum(len(r["evidence"]) for r in records) / len(records)
        if records
        else None,
        "empty_retrievals": sum(not r["evidence"] for r in records),
        "evaluation": summary(c.store.records("evaluations", 50)),
    }
