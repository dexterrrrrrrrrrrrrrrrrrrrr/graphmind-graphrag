import logging
from time import perf_counter
from uuid import uuid4

from backend.models.schemas import QueryResponse
from backend.reasoning.answers import generate
from backend.reasoning.providers import Provider

log = logging.getLogger(__name__)


class QueryService:
    def __init__(self, retriever, store):
        self.retriever, self.store = retriever, store

    def ask(self, request, settings, record=True, progress=None):
        request = request.model_copy(update={"mode": request.mode or settings.default_mode})
        start = perf_counter()
        if progress:
            progress("retrieving", {})
        strategy, reason, evidence, paths = self.retriever.retrieve(request, settings)
        retrieval_ms = (perf_counter() - start) * 1000
        generation_settings = settings.model_copy(
            update={"max_depth": request.max_depth or settings.max_depth}
        )
        answer, citations, usage, warnings = generate(
            request.question,
            evidence,
            paths,
            generation_settings,
            Provider(generation_settings, progress=progress),
        )
        cost = 0.0 if usage is not None else None  # API charges only; excludes local hardware/energy.
        result = QueryResponse(
            id=str(uuid4()),
            question=request.question,
            answer=answer,
            requested_mode=request.mode,
            strategy=strategy,
            routing_reason=reason,
            evidence=evidence,
            citations=citations,
            paths=paths,
            latency_ms=(perf_counter() - start) * 1000,
            retrieval_ms=retrieval_ms,
            token_usage=usage,
            estimated_cost_usd=cost,
            provider=settings.llm_provider,
            model=settings.llm_model,
            warnings=warnings,
        )
        log.info(
            "query_complete id=%s strategy=%s reason=%s latency_ms=%.1f",
            result.id,
            strategy,
            reason,
            result.latency_ms,
        )
        if record:
            self.store.record("queries", result.id, result.model_dump())
        return result
